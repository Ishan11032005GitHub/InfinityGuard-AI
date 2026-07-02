from datetime import datetime, timedelta
import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from ..auth import create_token, current_user, hash_password, token_pair, verify_password
from ..config import get_settings
from ..database import get_db
from ..models import AccountPreference, AuthSession, EmailVerificationToken, PasswordResetToken, Role, User
from ..schemas import AccountPreferencesIn, CompanyEmployeeCreateIn, EmailVerificationIn, ForgotPasswordIn, LoginIn, MFADisableIn, MFAEnableIn, PasswordChangeIn, ProfileUpdateIn, RefreshIn, ResetPasswordIn, SignupIn
from ..services.email_delivery import send_account_email
from ..services.mfa import new_secret, provisioning_uri, verify_totp
from ..services.audit import record_audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup")
def signup(payload: SignupIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    account_type = payload.account_type
    workspace_name = payload.workspace_name.strip() if payload.workspace_name else None
    if account_type == "individual":
        workspace_name = workspace_name or f"{payload.name}'s personal account"
    role = Role.admin if account_type == "individual" else payload.role
    user = User(
        email=payload.email,
        name=payload.name,
        account_type=account_type,
        workspace_name=workspace_name,
        workspace_key=secrets.token_urlsafe(24),
        role=role,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return token_pair(user, db)


@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email, User.is_active.is_(True)).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.mfa_enabled and (not payload.otp or not user.mfa_secret or not verify_totp(user.mfa_secret, payload.otp)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="A valid six-digit MFA code is required")
    return token_pair(user, db)


@router.post("/refresh")
def refresh(payload: RefreshIn, db: Session = Depends(get_db)):
    settings = get_settings()
    try:
        decoded = jwt.decode(payload.refresh_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if decoded.get("type") != "refresh" or not decoded.get("sid"):
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    user = db.query(User).filter(User.email == decoded.get("sub"), User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    session = db.query(AuthSession).filter(
        AuthSession.session_id == decoded["sid"],
        AuthSession.user_id == user.id,
        AuthSession.refresh_token_hash == hashlib.sha256(payload.refresh_token.encode()).hexdigest(),
        AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > datetime.utcnow(),
    ).first()
    if not session:
        raise HTTPException(status_code=401, detail="Refresh session has expired")
    return token_pair(user, db, revoke_session_id=session.session_id)


@router.post("/logout")
def logout(payload: RefreshIn, db: Session = Depends(get_db)):
    try:
        decoded = jwt.decode(payload.refresh_token, get_settings().jwt_secret, algorithms=[get_settings().jwt_algorithm])
    except JWTError:
        return {"status": "signed_out"}
    session_id = decoded.get("sid")
    if session_id:
        session = db.query(AuthSession).filter(AuthSession.session_id == session_id).first()
        if session and session.revoked_at is None:
            session.revoked_at = datetime.utcnow()
            db.commit()
    return {"status": "signed_out"}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role.value, "account_type": user.account_type, "workspace_name": user.workspace_name, "email_verified": user.email_verified, "mfa_enabled": user.mfa_enabled}


@router.patch("/me")
def update_me(payload: ProfileUpdateIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    user.name = payload.name.strip()
    db.commit()
    db.refresh(user)
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role.value, "account_type": user.account_type, "workspace_name": user.workspace_name}


def team_member_out(member: User):
    return {
        "id": member.id,
        "email": member.email,
        "name": member.name,
        "role": member.role.value,
        "account_type": member.account_type,
        "workspace_name": member.workspace_name,
        "is_active": member.is_active,
        "created_at": member.created_at.isoformat() if member.created_at else None,
    }


def require_company_admin(user: User):
    if user.account_type != "company" or user.role != Role.admin:
        raise HTTPException(status_code=403, detail="Only company admins can manage employee accounts")


@router.get("/company/users")
def company_users(db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_company_admin(user)
    members = db.query(User).filter(
        User.account_type == "company",
        User.workspace_key == user.workspace_key,
        User.is_active.is_(True),
    ).order_by(User.created_at.asc()).all()
    return [team_member_out(member) for member in members]


@router.post("/company/users")
def create_company_user(payload: CompanyEmployeeCreateIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_company_admin(user)
    if payload.role == Role.admin:
        raise HTTPException(status_code=400, detail="Create employee accounts as Viewer or Finance Manager")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    member = User(
        email=payload.email,
        name=payload.name.strip(),
        account_type="company",
        workspace_name=user.workspace_name,
        workspace_key=user.workspace_key,
        role=payload.role,
        hashed_password=hash_password(payload.password),
    )
    db.add(member)
    record_audit(
        db,
        user=user,
        action="company.member.created",
        entity_type="user",
        entity_id=member.id,
        details={"email": member.email, "role": member.role.value},
    )
    db.commit()
    db.refresh(member)
    return team_member_out(member)


@router.delete("/company/users/{member_id}")
def deactivate_company_user(member_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_company_admin(user)
    if member_id == user.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own admin account")
    member = db.query(User).filter(
        User.id == member_id,
        User.account_type == "company",
        User.workspace_key == user.workspace_key,
        User.is_active.is_(True),
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Employee account not found")
    member.is_active = False
    db.query(AuthSession).filter(
        AuthSession.user_id == member.id,
        AuthSession.revoked_at.is_(None),
    ).update({AuthSession.revoked_at: datetime.utcnow()}, synchronize_session=False)
    record_audit(
        db,
        user=user,
        action="company.member.deactivated",
        entity_type="user",
        entity_id=member.id,
        details={"email": member.email, "role": member.role.value},
    )
    db.commit()
    return {"status": "deactivated", "member_id": member.id}


@router.post("/password")
def change_password(payload: PasswordChangeIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).update(
        {AuthSession.revoked_at: datetime.utcnow()},
        synchronize_session=False,
    )
    db.commit()
    return {"status": "updated"}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordIn, db: Session = Depends(get_db)):
    result = {"message": "If this email is registered, a password reset link has been prepared."}
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return result
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=datetime.utcnow() + timedelta(minutes=30)))
    db.commit()
    settings = get_settings()
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"
    delivered = send_account_email(
        recipient=user.email,
        subject="Reset your LedgerOps password",
        heading="Reset your password",
        message="This secure link expires in 30 minutes.",
        action_url=reset_url,
        action_label="Reset password",
    )
    if settings.password_reset_preview and settings.environment != "production":
        result["reset_url"] = reset_url
    result["delivery"] = "email" if delivered else "preview" if "reset_url" in result else "not_configured"
    return result


@router.post("/reset-password")
def reset_password(payload: ResetPasswordIn, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    reset = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > datetime.utcnow(),
    ).first()
    if not reset:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired")
    user = db.get(User, reset.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Account could not be recovered")
    user.hashed_password = hash_password(payload.new_password)
    reset.used_at = datetime.utcnow()
    db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).update(
        {AuthSession.revoked_at: datetime.utcnow()},
        synchronize_session=False,
    )
    db.commit()
    return {"status": "updated", "message": "Password reset complete. You can now sign in."}


@router.post("/email-verification/request")
def request_email_verification(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.email_verified:
        return {"status": "verified"}
    token = secrets.token_urlsafe(32)
    db.add(EmailVerificationToken(
        user_id=user.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=datetime.utcnow() + timedelta(hours=24),
    ))
    db.commit()
    result = {"status": "sent", "message": "Verification instructions were prepared."}
    settings = get_settings()
    verification_url = f"{settings.frontend_url}/settings?verify_email={token}"
    delivered = send_account_email(
        recipient=user.email,
        subject="Verify your LedgerOps email",
        heading="Verify your email address",
        message="Verification protects account recovery and live financial operations. This link expires in 24 hours.",
        action_url=verification_url,
        action_label="Verify email",
    )
    if settings.password_reset_preview and settings.environment != "production":
        result["verification_url"] = verification_url
    result["delivery"] = "email" if delivered else "preview" if "verification_url" in result else "not_configured"
    return result


@router.post("/email-verification/confirm")
def confirm_email_verification(payload: EmailVerificationIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    token = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id,
        EmailVerificationToken.token_hash == token_hash,
        EmailVerificationToken.used_at.is_(None),
        EmailVerificationToken.expires_at > datetime.utcnow(),
    ).first()
    if not token:
        raise HTTPException(status_code=400, detail="Verification link is invalid or expired")
    user.email_verified = True
    token.used_at = datetime.utcnow()
    db.commit()
    return {"status": "verified"}


@router.post("/mfa/setup")
def setup_mfa(db: Session = Depends(get_db), user: User = Depends(current_user)):
    secret = new_secret()
    user.mfa_secret = secret
    user.mfa_enabled = False
    db.commit()
    return {"secret": secret, "provisioning_uri": provisioning_uri(secret, user.email)}


@router.post("/mfa/enable")
def enable_mfa(payload: MFAEnableIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not user.mfa_secret or not verify_totp(user.mfa_secret, payload.code):
        raise HTTPException(status_code=400, detail="The MFA code is invalid")
    user.mfa_enabled = True
    db.commit()
    return {"status": "enabled"}


@router.post("/mfa/disable")
def disable_mfa(payload: MFADisableIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Password is incorrect")
    if not user.mfa_secret or not verify_totp(user.mfa_secret, payload.code):
        raise HTTPException(status_code=400, detail="The MFA code is invalid")
    user.mfa_enabled = False
    user.mfa_secret = None
    db.commit()
    return {"status": "disabled"}


def preferences_out(preferences: AccountPreference):
    return {
        "paymentAlerts": preferences.payment_alerts,
        "riskAlerts": preferences.risk_alerts,
        "weeklyDigest": preferences.weekly_digest,
        "currency": preferences.currency,
        "timezone": preferences.timezone,
        "oneTimePaymentLimit": preferences.one_time_payment_limit,
    }


@router.get("/preferences")
def get_preferences(db: Session = Depends(get_db), user: User = Depends(current_user)):
    preferences = db.query(AccountPreference).filter(AccountPreference.user_id == user.id).first()
    if not preferences:
        preferences = AccountPreference(user_id=user.id)
        db.add(preferences)
        db.commit()
        db.refresh(preferences)
    return preferences_out(preferences)


@router.patch("/preferences")
def update_preferences(payload: AccountPreferencesIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    preferences = db.query(AccountPreference).filter(AccountPreference.user_id == user.id).first()
    if not preferences:
        preferences = AccountPreference(user_id=user.id)
        db.add(preferences)
    preferences.payment_alerts = payload.paymentAlerts
    preferences.risk_alerts = payload.riskAlerts
    preferences.weekly_digest = payload.weeklyDigest
    preferences.currency = payload.currency
    preferences.timezone = payload.timezone
    preferences.one_time_payment_limit = payload.oneTimePaymentLimit
    db.commit()
    db.refresh(preferences)
    return preferences_out(preferences)

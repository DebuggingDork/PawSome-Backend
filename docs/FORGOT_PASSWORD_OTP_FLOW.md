# Forgot Password OTP Flow

## Overview
Secure password reset flow using 6-digit OTP codes delivered via Brevo email service.

## Features

### Backend (Python/FastAPI)
- **New Endpoints:**
  - `POST /auth/forgot-password-otp` - Send OTP to email
  - `POST /auth/verify-password-reset-otp` - Verify OTP code
  - `POST /auth/reset-password-with-otp` - Reset password with verified OTP

- **Security Features:**
  - 6-digit cryptographically secure OTP codes
  - 10-minute expiration
  - Maximum 5 attempts per code
  - Rate limiting (60-second cooldown between requests)
  - Constant-time comparison to prevent timing attacks
  - Email enumeration prevention (always returns success message)

- **Email Service (Brevo):**
  - Beautiful HTML email templates matching brand design
  - Plain text fallback
  - OTP code prominently displayed
  - Clear expiration messaging

### Frontend (React/TypeScript)
- **New Page:** `/forgot-password`
- **Multi-Step Flow:**
  1. **Email Entry** - User enters email address
  2. **OTP Verification** - 6-digit code input with validation
  3. **New Password** - Set new password with confirmation
  4. **Success** - Confirmation and redirect to sign in

- **UX Features:**
  - Smooth animations between steps
  - Real-time validation
  - Clear error messages
  - Resend code functionality
  - Back navigation between steps
  - Matching design aesthetic with existing auth pages
  - Gradient backgrounds and glassmorphism effects
  - Loading states and disabled button states

## User Flow

```
1. User clicks "Forgot password?" on sign-in page
   ↓
2. Redirected to /forgot-password
   ↓
3. Enter email address → Click "Send Code"
   ↓
4. OTP sent via email (6-digit code)
   ↓
5. Enter OTP code → Click "Verify Code"
   ↓
6. Enter new password (with confirmation)
   ↓
7. Click "Reset Password"
   ↓
8. Success message → Redirect to sign in
```

## API Examples

### Send OTP
```typescript
POST /auth/forgot-password-otp
{
  "email": "user@example.com"
}

Response:
{
  "message": "If the email exists, a password reset code has been sent",
  "retry_after_seconds": 60,
  "delivered": true
}
```

### Verify OTP
```typescript
POST /auth/verify-password-reset-otp
{
  "email": "user@example.com",
  "code": "123456"
}

Response:
{
  "message": "Code verified successfully"
}
```

### Reset Password
```typescript
POST /auth/reset-password-with-otp
{
  "email": "user@example.com",
  "code": "123456",
  "new_password": "NewSecurePassword123!"
}

Response:
{
  "message": "Password has been reset successfully"
}
```

## Error Handling

### Backend Errors
- `400 Bad Request` - Invalid/expired code, passwords don't match
- `429 Too Many Requests` - Too many attempts or resend requests
- `404 Not Found` - User not found (internal only)

### Frontend Error Messages
- "That code has expired. Request a new one."
- "Too many incorrect attempts. Request a new code."
- "That code isn't right. Check the email and try again."
- "Passwords do not match."
- "Could not reach the server. Please check your connection."

## Security Considerations

1. **Email Enumeration Protection:** Always returns generic success message
2. **Brute Force Protection:** 5-attempt limit per code, 60-second cooldown
3. **Code Expiration:** 10-minute lifetime
4. **Single-Use Codes:** Code deleted after successful password reset
5. **Constant-Time Comparison:** Prevents timing attacks on code validation
6. **Secure Random:** Uses `secrets.randbelow()` for cryptographic randomness

## Email Template

The OTP email includes:
- PawSome branding
- Large, centered 6-digit code
- Expiration notice
- Consistent styling with verification emails
- Mobile-responsive design

## Fallback Flow

The original token-based password reset flow (`/auth/forgot-password` and `/auth/reset-password`) remains available as a fallback for:
- Email clients that can't display the code properly
- Users who prefer link-based resets
- Integration with external systems

## Testing

### Manual Testing
1. Navigate to `/forgot-password`
2. Enter test email address
3. Check email for OTP code
4. Enter code in UI
5. Set new password
6. Verify can sign in with new password

### Edge Cases to Test
- Invalid email format
- Non-existent email
- Expired OTP
- Wrong OTP (multiple attempts)
- Rate limiting (rapid resend requests)
- Password mismatch
- Network errors

## Future Enhancements

- SMS OTP as alternative delivery method
- Remember device to skip OTP on trusted devices
- Account recovery questions
- Multi-factor authentication integration
- Biometric authentication support

## Files Modified/Created

### Backend
- `app/schemas/auth.py` - New schema classes
- `app/services/email.py` - OTP generation and verification
- `app/api/routes/auth.py` - New endpoints

### Frontend
- `src/pages/ForgotPassword/index.tsx` - New page component
- `src/lib/api/auth.ts` - API client functions
- `src/App.tsx` - Route configuration
- `src/pages/Auth/index.tsx` - Updated forgot password link

## Commits
1. Backend: `feat: add OTP-based password reset flow with Brevo email delivery`
2. Frontend: `feat: add beautiful OTP-based forgot password UI with multi-step flow`

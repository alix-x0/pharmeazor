import { useState, useEffect } from "react";
import api from "@/api/api";

/* ─── Icons ─── */
const EyeIcon = ({ open }) =>
    open ? (
        <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z" />
            <circle cx="12" cy="12" r="3" />
        </svg>
    ) : (
        <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
            <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" />
            <line x1="1" y1="1" x2="23" y2="23" />
        </svg>
    );

const CloseIcon = () => (
    <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <line x1="18" y1="6" x2="6" y2="18" />
        <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
);

const MailIcon = () => (
    <svg width="40" height="40" fill="none" viewBox="0 0 24 24" className="text-purple-500">
        <rect x="2" y="4" width="20" height="16" rx="3" stroke="currentColor" strokeWidth="1.5" />
        <path d="M22 7l-10 6L2 7" stroke="currentColor" strokeWidth="1.5" />
    </svg>
);

const ShieldIcon = () => (
    <svg width="40" height="40" fill="none" viewBox="0 0 24 24" className="text-purple-500">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" stroke="currentColor" strokeWidth="1.5" />
        <path d="M9 12l2 2 4-4" stroke="currentColor" strokeWidth="1.5" />
    </svg>
);

const LockIcon = () => (
    <svg width="40" height="40" fill="none" viewBox="0 0 24 24" className="text-purple-500">
        <rect x="3" y="11" width="18" height="11" rx="2" stroke="currentColor" strokeWidth="1.5" />
        <path d="M7 11V7a5 5 0 0110 0v4" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="12" cy="16" r="1" fill="currentColor" />
    </svg>
);

const CheckCircleIcon = () => (
    <svg width="56" height="56" fill="none" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" stroke="#22c55e" strokeWidth="1.5" />
        <path d="M8 12l2.5 2.5L16 9" stroke="#22c55e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
);

/* ─── Step Dots ─── */
const StepDots = ({ current, total = 3 }) => (
    <div className="flex items-center justify-center gap-1.5 mb-5">
        {[...Array(total)].map((_, i) => (
            <div
                key={i}
                className={`rounded-full transition-all duration-400 ${i === current
                    ? "w-6 h-2 bg-gradient-to-r from-purple-600 to-pink-500"
                    : i < current
                        ? "w-2 h-2 bg-purple-400"
                        : "w-2 h-2 bg-indigo-200"
                    }`}
            />
        ))}
    </div>
);

/* ════════════════════════════════════════════
   ForgotPasswordModal Component
   ════════════════════════════════════════════ */
function ForgotPasswordModal({ isOpen, onClose }) {
    const [step, setStep] = useState(0);
    const [email, setEmail] = useState("");
    const [otp, setOtp] = useState(["", "", "", "", "", ""]);
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [showPw, setShowPw] = useState(false);
    const [showConfirmPw, setShowConfirmPw] = useState(false);
    const [loading, setLoading] = useState(false);
    const [errors, setErrors] = useState({});
    const [resendTimer, setResendTimer] = useState(0);
    const [closing, setClosing] = useState(false);

    // Reset everything when modal opens
    useEffect(() => {
        if (isOpen) {
            setStep(0);
            setEmail("");
            setOtp(["", "", "", "", "", ""]);
            setNewPassword("");
            setConfirmPassword("");
            setShowPw(false);
            setShowConfirmPw(false);
            setErrors({});
            setClosing(false);
        }
    }, [isOpen]);

    // Close with animation
    const handleClose = () => {
        setClosing(true);
        setTimeout(() => {
            setClosing(false);
            onClose();
        }, 250);
    };

    // Close on Escape
    useEffect(() => {
        const handleKey = (e) => {
            if (e.key === "Escape" && isOpen) handleClose();
        };
        window.addEventListener("keydown", handleKey);
        return () => window.removeEventListener("keydown", handleKey);
    }, [isOpen]);

    if (!isOpen) return null;

    /* ─── Timer for resend OTP ─── */
    const startResendTimer = () => {
        setResendTimer(60);
        const interval = setInterval(() => {
            setResendTimer((prev) => {
                if (prev <= 1) { clearInterval(interval); return 0; }
                return prev - 1;
            });
        }, 1000);
    };

    /* ─── Step 1: Submit Email ─── */
    const handleEmailSubmit = async (e) => {
        e.preventDefault();
        if (!email.trim()) { setErrors({ email: "Please enter your email address." }); return; }
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setErrors({ email: "Please enter a valid email." }); return; }
        setErrors({});
        setLoading(true);
        try {
            await api.post("/auth/forgot-password/", { email });
            setStep(1);
            startResendTimer();
        } catch (error) {
            setErrors({ email: error.response?.status === 404 ? "No account found with this email." : "Something went wrong." });
        } finally { setLoading(false); }
    };

    /* ─── Step 2: OTP ─── */
    const handleOtpChange = (index, value) => {
        if (value.length > 1) value = value.slice(-1);
        if (!/^\d*$/.test(value)) return;
        const newOtp = [...otp];
        newOtp[index] = value;
        setOtp(newOtp);
        setErrors({});
        if (value && index < 5) document.getElementById(`otp-${index + 1}`)?.focus();
    };

    const handleOtpKeyDown = (index, e) => {
        if (e.key === "Backspace" && !otp[index] && index > 0)
            document.getElementById(`otp-${index - 1}`)?.focus();
    };

    const handleOtpPaste = (e) => {
        e.preventDefault();
        const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
        if (pasted.length > 0) {
            const newOtp = [...otp];
            for (let i = 0; i < 6; i++) newOtp[i] = pasted[i] || "";
            setOtp(newOtp);
            document.getElementById(`otp-${Math.min(pasted.length, 5)}`)?.focus();
        }
    };

    const handleOtpSubmit = async (e) => {
        e.preventDefault();
        const code = otp.join("");
        if (code.length !== 6) { setErrors({ otp: "Please enter the 6-digit code." }); return; }
        setErrors({});
        setLoading(true);
        try {
            await api.post("/auth/verify-reset-code/", { email, code });
            setStep(2);
        } catch { setErrors({ otp: "Invalid or expired code." }); }
        finally { setLoading(false); }
    };

    /* ─── Step 3: New Password ─── */
    const handlePasswordSubmit = async (e) => {
        e.preventDefault();
        let newErrors = {};
        if (!newPassword) newErrors.newPassword = "Please enter a new password.";
        else if (newPassword.length < 8) newErrors.newPassword = "Must be at least 8 characters.";
        if (!confirmPassword) newErrors.confirmPassword = "Please confirm your password.";
        else if (newPassword !== confirmPassword) newErrors.confirmPassword = "Passwords do not match.";
        if (Object.keys(newErrors).length > 0) { setErrors(newErrors); return; }
        setErrors({});
        setLoading(true);
        try {
            await api.post("/auth/reset-password/", { email, code: otp.join(""), new_password: newPassword });
            setStep(3);
        } catch { setErrors({ newPassword: "Failed to reset password." }); }
        finally { setLoading(false); }
    };

    const handleResend = async () => {
        if (resendTimer > 0) return;
        setLoading(true);
        try {
            await api.post("/auth/forgot-password/", { email });
            startResendTimer();
            setOtp(["", "", "", "", "", ""]);
        } catch { setErrors({ otp: "Failed to resend." }); }
        finally { setLoading(false); }
    };

    const stepIcons = [<MailIcon />, <ShieldIcon />, <LockIcon />];
    const stepTitles = ["Forgot Password?", "Verify Code", "New Password"];
    const stepSubtitles = [
        "No worries! Enter your email and we'll send you a reset code.",
        <>We sent a 6-digit code to <strong className="text-indigo-950">{email}</strong></>,
        "Create a strong new password for your account.",
    ];

    return (
        <>
            {/* ─── Backdrop ─── */}
            <div
                className={`fixed inset-0 z-[999] flex items-center justify-center p-4 transition-all duration-300 ${closing ? "opacity-0" : "opacity-100"
                    }`}
                onClick={handleClose}
            >
                {/* Blurred overlay */}
                <div className="absolute inset-0 bg-indigo-950/40 backdrop-blur-sm" />

                {/* ─── Modal Card ─── */}
                <div
                    className={`relative z-10 w-full max-w-[420px] bg-white rounded-3xl shadow-[0_25px_60px_rgba(124,58,237,0.18),0_8px_24px_rgba(0,0,0,0.08)] overflow-hidden transition-all duration-300 ${closing
                        ? "opacity-0 scale-95 translate-y-4"
                        : "opacity-100 scale-100 translate-y-0 animate-[modalIn_0.35s_cubic-bezier(0.22,1,0.36,1)_forwards]"
                        }`}
                    onClick={(e) => e.stopPropagation()}
                >
                    {/* Purple accent bar at top */}
                    <div
                        className="h-1.5 w-full"
                        style={{ background: "linear-gradient(90deg, #7c3aed 0%, #ec4899 100%)" }}
                    />

                    {/* Close button */}
                    <button
                        onClick={handleClose}
                        className="absolute top-4 right-4 z-20 w-8 h-8 rounded-full bg-gray-100 hover:bg-red-50 flex items-center justify-center text-gray-400 hover:text-red-500 transition-all cursor-pointer border-none hover:rotate-90 duration-300"
                        aria-label="Close"
                    >
                        <CloseIcon />
                    </button>

                    {/* Content area */}
                    <div className="px-8 pt-7 pb-8">

                        {step < 3 && (
                            <>
                                <StepDots current={step} />

                                {/* Icon */}
                                <div className="flex justify-center mb-3">
                                    <div className="w-14 h-14 rounded-2xl bg-purple-50 border border-purple-100 flex items-center justify-center shadow-sm">
                                        {stepIcons[step]}
                                    </div>
                                </div>

                                {/* Title */}
                                <h2 className="text-center text-lg font-bold text-indigo-950 mb-1">
                                    {stepTitles[step]}
                                </h2>
                                <p className="text-center text-[13px] text-gray-400 mb-5 leading-relaxed px-2">
                                    {stepSubtitles[step]}
                                </p>
                            </>
                        )}

                        {/* ── Step 0: Email ── */}
                        {step === 0 && (
                            <form onSubmit={handleEmailSubmit} className="flex flex-col gap-3.5" noValidate>
                                <div className="flex flex-col gap-1">
                                    <label htmlFor="forgot-email" className="text-xs font-semibold text-indigo-900">
                                        Email Address
                                    </label>
                                    <input
                                        id="forgot-email"
                                        type="email"
                                        value={email}
                                        onChange={(e) => { setEmail(e.target.value); setErrors({}); }}
                                        placeholder="Enter your email"
                                        autoComplete="email"
                                        autoFocus
                                        className={`w-full px-3.5 py-2.5 border-[1.5px] rounded-xl text-sm text-indigo-950 bg-indigo-50/30 outline-none transition-all placeholder:text-indigo-300 focus:ring-[3px] focus:bg-white ${errors.email ? "border-red-400 focus:border-red-500 focus:ring-red-400/20" : "border-indigo-100 focus:border-purple-600 focus:ring-purple-600/10"
                                            }`}
                                    />
                                    {errors.email && (
                                        <span className="text-red-500 text-xs mt-0.5 ml-1 flex items-center gap-1">
                                            <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                                            {errors.email}
                                        </span>
                                    )}
                                </div>
                                <button
                                    type="submit"
                                    disabled={loading}
                                    className="w-full py-2.5 border-none rounded-xl text-sm font-semibold text-white cursor-pointer flex items-center justify-center min-h-[42px] transition-all hover:translate-y-[-1px] hover:shadow-[0_6px_22px_rgba(124,58,237,0.35)] active:translate-y-0 disabled:opacity-70 disabled:cursor-not-allowed"
                                    style={{ background: "linear-gradient(135deg, #7c3aed 0%, #ec4899 100%)" }}
                                >
                                    {loading ? <span className="w-5 h-5 border-[2.5px] border-white/30 border-t-white rounded-full animate-spin" /> : "Send Reset Code"}
                                </button>
                            </form>
                        )}

                        {/* ── Step 1: OTP ── */}
                        {step === 1 && (
                            <form onSubmit={handleOtpSubmit} className="flex flex-col gap-3.5" noValidate>
                                <div className="flex flex-col gap-2">
                                    <div className="flex justify-center gap-2" onPaste={handleOtpPaste}>
                                        {otp.map((digit, i) => (
                                            <input
                                                key={i}
                                                id={`otp-${i}`}
                                                type="text"
                                                inputMode="numeric"
                                                maxLength={1}
                                                value={digit}
                                                onChange={(e) => handleOtpChange(i, e.target.value)}
                                                onKeyDown={(e) => handleOtpKeyDown(i, e)}
                                                autoFocus={i === 0}
                                                className={`w-10 h-11 text-center text-lg font-bold rounded-xl border-[1.5px] outline-none transition-all bg-indigo-50/30 text-indigo-950 focus:ring-[3px] focus:bg-white ${errors.otp
                                                    ? "border-red-400 focus:border-red-500 focus:ring-red-400/20 animate-[shake_0.4s_ease-in-out]"
                                                    : digit
                                                        ? "border-purple-400 focus:border-purple-600 focus:ring-purple-600/10"
                                                        : "border-indigo-100 focus:border-purple-600 focus:ring-purple-600/10"
                                                    }`}
                                            />
                                        ))}
                                    </div>
                                    {errors.otp && (
                                        <span className="text-red-500 text-xs text-center flex items-center justify-center gap-1">
                                            <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                                            {errors.otp}
                                        </span>
                                    )}
                                </div>
                                <button
                                    type="submit"
                                    disabled={loading}
                                    className="w-full py-2.5 border-none rounded-xl text-sm font-semibold text-white cursor-pointer flex items-center justify-center min-h-[42px] transition-all hover:translate-y-[-1px] hover:shadow-[0_6px_22px_rgba(124,58,237,0.35)] active:translate-y-0 disabled:opacity-70 disabled:cursor-not-allowed"
                                    style={{ background: "linear-gradient(135deg, #7c3aed 0%, #ec4899 100%)" }}
                                >
                                    {loading ? <span className="w-5 h-5 border-[2.5px] border-white/30 border-t-white rounded-full animate-spin" /> : "Verify Code"}
                                </button>
                                <p className="text-center text-[13px] text-gray-400">
                                    Didn't receive it?{" "}
                                    {resendTimer > 0 ? (
                                        <span className="text-indigo-300 font-medium">Resend in {resendTimer}s</span>
                                    ) : (
                                        <button type="button" onClick={handleResend} disabled={loading}
                                            className="bg-transparent border-none text-purple-600 font-semibold cursor-pointer hover:text-purple-800 hover:underline p-0 text-[13px]">
                                            Resend Code
                                        </button>
                                    )}
                                </p>
                            </form>
                        )}

                        {/* ── Step 2: New Password ── */}
                        {step === 2 && (
                            <form onSubmit={handlePasswordSubmit} className="flex flex-col gap-3.5" noValidate>
                                <div className="flex flex-col gap-1">
                                    <label htmlFor="new-password" className="text-xs font-semibold text-indigo-900">New Password</label>
                                    <div className="relative">
                                        <input
                                            id="new-password"
                                            type={showPw ? "text" : "password"}
                                            value={newPassword}
                                            onChange={(e) => { setNewPassword(e.target.value); setErrors((p) => ({ ...p, newPassword: null })); }}
                                            placeholder="Enter new password"
                                            autoFocus
                                            className={`w-full px-3.5 py-2.5 pr-10 border-[1.5px] rounded-xl text-sm text-indigo-950 bg-indigo-50/30 outline-none transition-all placeholder:text-indigo-300 focus:ring-[3px] focus:bg-white ${errors.newPassword ? "border-red-400 focus:border-red-500 focus:ring-red-400/20" : "border-indigo-100 focus:border-purple-600 focus:ring-purple-600/10"
                                                }`}
                                        />
                                        <button type="button" onClick={() => setShowPw(!showPw)}
                                            className="absolute right-2.5 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer text-indigo-300 hover:text-purple-600 transition-colors p-0 flex items-center" tabIndex={-1}>
                                            <EyeIcon open={showPw} />
                                        </button>
                                    </div>
                                    {errors.newPassword && (
                                        <span className="text-red-500 text-xs mt-0.5 ml-1 flex items-center gap-1">
                                            <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                                            {errors.newPassword}
                                        </span>
                                    )}
                                </div>

                                <div className="flex flex-col gap-1">
                                    <label htmlFor="confirm-password" className="text-xs font-semibold text-indigo-900">Confirm Password</label>
                                    <div className="relative">
                                        <input
                                            id="confirm-password"
                                            type={showConfirmPw ? "text" : "password"}
                                            value={confirmPassword}
                                            onChange={(e) => { setConfirmPassword(e.target.value); setErrors((p) => ({ ...p, confirmPassword: null })); }}
                                            placeholder="Confirm new password"
                                            className={`w-full px-3.5 py-2.5 pr-10 border-[1.5px] rounded-xl text-sm text-indigo-950 bg-indigo-50/30 outline-none transition-all placeholder:text-indigo-300 focus:ring-[3px] focus:bg-white ${errors.confirmPassword ? "border-red-400 focus:border-red-500 focus:ring-red-400/20" : "border-indigo-100 focus:border-purple-600 focus:ring-purple-600/10"
                                                }`}
                                        />
                                        <button type="button" onClick={() => setShowConfirmPw(!showConfirmPw)}
                                            className="absolute right-2.5 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer text-indigo-300 hover:text-purple-600 transition-colors p-0 flex items-center" tabIndex={-1}>
                                            <EyeIcon open={showConfirmPw} />
                                        </button>
                                    </div>
                                    {errors.confirmPassword && (
                                        <span className="text-red-500 text-xs mt-0.5 ml-1 flex items-center gap-1">
                                            <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                                            {errors.confirmPassword}
                                        </span>
                                    )}
                                </div>

                                {/* Password strength */}
                                <div className="flex items-center gap-2 px-1">
                                    <div className="flex-1 flex gap-1">
                                        {[...Array(4)].map((_, i) => (
                                            <div key={i} className={`h-1 flex-1 rounded-full transition-all duration-300 ${newPassword.length === 0 ? "bg-gray-200"
                                                : newPassword.length < 4 ? (i === 0 ? "bg-red-400" : "bg-gray-200")
                                                    : newPassword.length < 8 ? (i < 2 ? "bg-yellow-400" : "bg-gray-200")
                                                        : newPassword.length < 12 ? (i < 3 ? "bg-purple-400" : "bg-gray-200")
                                                            : "bg-green-400"
                                                }`} />
                                        ))}
                                    </div>
                                    <span className="text-[10px] text-gray-400 w-14">
                                        {newPassword.length === 0 ? "" : newPassword.length < 4 ? "Weak" : newPassword.length < 8 ? "Fair" : newPassword.length < 12 ? "Strong" : "Very Strong"}
                                    </span>
                                </div>

                                <button
                                    type="submit"
                                    disabled={loading}
                                    className="w-full py-2.5 border-none rounded-xl text-sm font-semibold text-white cursor-pointer flex items-center justify-center min-h-[42px] transition-all hover:translate-y-[-1px] hover:shadow-[0_6px_22px_rgba(124,58,237,0.35)] active:translate-y-0 disabled:opacity-70 disabled:cursor-not-allowed"
                                    style={{ background: "linear-gradient(135deg, #7c3aed 0%, #ec4899 100%)" }}
                                >
                                    {loading ? <span className="w-5 h-5 border-[2.5px] border-white/30 border-t-white rounded-full animate-spin" /> : "Reset Password"}
                                </button>
                            </form>
                        )}

                        {/* ── Step 3: Success ── */}
                        {step === 3 && (
                            <div className="flex flex-col items-center gap-3 py-4">
                                <div className="animate-[scaleIn_0.4s_cubic-bezier(0.22,1,0.36,1)_forwards]">
                                    <CheckCircleIcon />
                                </div>
                                <h2 className="text-lg font-bold text-indigo-950">Password Reset!</h2>
                                <p className="text-[13px] text-gray-400 text-center leading-relaxed">
                                    Your password has been reset successfully.<br />
                                    You can now sign in with your new password.
                                </p>
                                <button
                                    onClick={handleClose}
                                    className="mt-1 w-full py-2.5 border-none rounded-xl text-sm font-semibold text-white cursor-pointer flex items-center justify-center min-h-[42px] transition-all hover:translate-y-[-1px] hover:shadow-[0_6px_22px_rgba(124,58,237,0.35)] active:translate-y-0"
                                    style={{ background: "linear-gradient(135deg, #7c3aed 0%, #ec4899 100%)" }}
                                >
                                    Back to Sign In
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Keyframes */}
            <style>{`
                @keyframes modalIn {
                    from { opacity: 0; transform: scale(0.92) translateY(20px); }
                    to   { opacity: 1; transform: scale(1) translateY(0); }
                }
                @keyframes scaleIn {
                    from { opacity: 0; transform: scale(0.5); }
                    to   { opacity: 1; transform: scale(1); }
                }
                @keyframes shake {
                    0%, 100% { transform: translateX(0); }
                    20% { transform: translateX(-4px); }
                    40% { transform: translateX(4px); }
                    60% { transform: translateX(-4px); }
                    80% { transform: translateX(4px); }
                }
            `}</style>
        </>
    );
}

export default ForgotPasswordModal;

import React, { useState } from "react";
import axios from "axios";
import { QRCodeSVG } from "qrcode.react";
import { useNavigate } from "react-router-dom";

const API_BASE_URL = "http://localhost:5000";

export default function RegisterPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [enable2FA, setEnable2FA] = useState(false);
    const [qrUri, setQrUri] = useState(null);
    const [secret, setSecret] = useState(null);
    const [error, setError] = useState(null);
    const navigate = useNavigate();

    const isValidEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    const isValidPassword = (password) =>
        /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/.test(password);

    const handleRegister = async (e) => {
        e.preventDefault();
        setError(null);
        setQrUri(null);
        setSecret(null);

        if (!isValidEmail(email)) {
            setError("Please enter a valid email.");
            return;
        }

        if (!isValidPassword(password)) {
            setError("Password must be at least 8 characters, include uppercase, lowercase, and a number.");
            return;
        }

        if (password !== confirmPassword) {
            setError("Passwords do not match.");
            return;
        }

        try {
            const response = await axios.post(`${API_BASE_URL}/auth/register`, {
                email,
                password,
                enable_2fa: enable2FA,
            });

            if (response.data.qr_uri) {
                setQrUri(response.data.qr_uri);
                setSecret(response.data.secret);
                alert("Registration successful! Please set up your 2FA.");

            } else {
                alert("User registered successfully! You can now log in.");
                navigate("/login");
            }
        } catch (err) {
            setError(err.response?.data?.error || "Registration failed. Please try again.");
            console.error("Registration error:", err.response || err);
        }
    };

    const goToLogin = () => {
        navigate("/login");
    };

    return (
        <div className="register-container" style={{ maxWidth: '400px', margin: '0 auto', padding: '20px', fontFamily: 'Arial, sans-serif' }}>
            <h2 style={{ textAlign: 'center', marginBottom: '20px' }}>Create Account</h2>

            {error && (
                <div style={{
                    backgroundColor: '#ffebee', color: '#c62828', padding: '10px',
                    borderRadius: '4px', marginBottom: '20px', textAlign: 'center'
                }}>
                    {error}
                </div>
            )}

            {!qrUri ? (
                <form onSubmit={handleRegister}>
                    <div style={{ marginBottom: '15px' }}>
                        <label htmlFor="emailReg" style={{ display: 'block', marginBottom: '5px' }}>Email:</label>
                        <input
                            id="emailReg"
                            type="email"
                            placeholder="Enter your email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                            style={{ width: 'calc(100% - 20px)', padding: '10px', borderRadius: '4px', border: '1px solid #ccc' }}
                        />
                    </div>

                    <div style={{ marginBottom: '15px' }}>
                        <label htmlFor="passwordReg" style={{ display: 'block', marginBottom: '5px' }}>Password:</label>
                        <input
                            id="passwordReg"
                            type="password"
                            placeholder="Create a password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            style={{ width: 'calc(100% - 20px)', padding: '10px', borderRadius: '4px', border: '1px solid #ccc' }}
                        />
                    </div>

                    <div style={{ marginBottom: '15px' }}>
                        <label htmlFor="confirmPasswordReg" style={{ display: 'block', marginBottom: '5px' }}>Confirm Password:</label>
                        <input
                            id="confirmPasswordReg"
                            type="password"
                            placeholder="Confirm your password"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            required
                            style={{ width: 'calc(100% - 20px)', padding: '10px', borderRadius: '4px', border: '1px solid #ccc' }}
                        />
                    </div>

                    <div style={{ marginBottom: '20px', display: 'flex', alignItems: 'center' }}>
                        <input
                            type="checkbox"
                            id="enable2fa"
                            checked={enable2FA}
                            onChange={(e) => setEnable2FA(e.target.checked)}
                            style={{ marginRight: '10px', transform: 'scale(1.2)' }}
                        />
                        <label htmlFor="enable2fa">Enable Two-Factor Authentication</label>
                    </div>

                    <button type="submit" style={{  width: '100%', padding: '12px', backgroundColor: '#4CAF50', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                        Create Account
                    </button>
                </form>
            ) : (
                <div style={{ marginTop: '20px', padding: '15px', border: '1px solid #e0e0e0', borderRadius: '4px', backgroundColor: '#f9f9f9', textAlign: 'center' }}>
                    <h3>Set Up Two-Factor Authentication</h3>
                    <p>Scan this QR code with your authenticator app (e.g., Google Authenticator, Authy):</p>
                    <div style={{ margin: '20px 0' }}>
                        <QRCodeSVG value={qrUri} size={200} />
                    </div>
                    {secret && (
                        <p style={{ fontSize: '14px', color: '#555', wordBreak: 'break-all' }}>
                            Or manually enter this secret key: <strong>{secret}</strong>
                        </p>
                    )}
                    <p style={{ fontSize: '14px', color: '#333', marginTop: '15px' }}>
                        After scanning and setting up in your app, click below to log in.
                    </p>
                    <button onClick={goToLogin} style={{ marginTop: '15px', padding: '10px 20px', backgroundColor: '#2196F3', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                        I've Set Up 2FA, Go to Login
                    </button>
                </div>
            )}

            <div style={{ marginTop: '20px', textAlign: 'center' }}>
                <p>
                    Already have an account?{' '}
                    <button onClick={goToLogin} style={{ background: 'none', border: 'none', color: '#2196F3', fontWeight: 'bold', cursor: 'pointer', padding: '0', fontSize: '1em' }}>
                        Log In
                    </button>
                </p>
            </div>
        </div>
    );
}
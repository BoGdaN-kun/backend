import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const API_BASE_URL = "http://localhost:5000";

function LoginPage() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [otp, setOtp] = useState('');
    const [error, setError] = useState(null);
    const [message, setMessage] = useState(null);
    const [otpRequired, setOtpRequired] = useState(false);

    const navigate = useNavigate();


    const isValidEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    const isValidPassword = (password) => password.length >= 6;
    const isValidOTP = (otp) => /^\d{6}$/.test(otp);

    const handleSuccessfulLogin = (token, successMessage) => {

        localStorage.setItem('authToken', token);

        setMessage(successMessage || 'Login successful!');
        setError(null);
        setTimeout(() => {
            navigate('/portfolio');
        }, 1000);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setMessage(null);

        try {
            if (!otpRequired) {
                if (!isValidEmail(email)) {
                    setError("Please enter a valid email address.");
                    return;
                }
                if (!isValidPassword(password)) {
                    setError("Password must be at least 6 characters.");
                    return;
                }

                const response = await fetch(`${API_BASE_URL}/auth/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password }),
                });

                const data = await response.json();

                if (response.ok) {
                    if (data.otp_required) {
                        setOtpRequired(true);
                        setMessage(data.message || 'OTP is required to complete login.');
                        setPassword('');
                    } else if (data.access_token) {
                        handleSuccessfulLogin(data.access_token, data.message);
                    } else {

                        setError("Login response was OK but didn't provide token or OTP requirement.");
                    }
                } else {
                    setError(data.error || `Login failed (Status: ${response.status})`);
                }
            } else {
                if (!isValidOTP(otp)) {
                    setError("OTP must be a 6-digit number.");
                    return;
                }

                const response = await fetch(`${API_BASE_URL}/auth/verify-otp`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ email, otp }),
                });

                const data = await response.json();

                if (response.ok && data.access_token) {
                    handleSuccessfulLogin(data.access_token, data.message);
                } else {
                    setError(data.error || `OTP verification failed (Status: ${response.status})`);
                }
            }
        } catch (err) {
            console.error("Login/OTP Error:", err);
            setError('A network error occurred or the server is unreachable. Please try again.');
        }
    };

    return (
        <div className="login-container" style={{ maxWidth: '400px', margin: '0 auto', padding: '20px', fontFamily: 'Arial, sans-serif' }}>
            <h2>Login</h2>
            {error && <div style={{ color: 'red', backgroundColor: '#ffebee', padding: '10px', marginBottom: '10px', borderRadius: '4px', textAlign: 'center' }}>{error}</div>}
            {message && !error && <div style={{ color: 'green', backgroundColor: '#e8f5e9', padding: '10px', marginBottom: '10px', borderRadius: '4px', textAlign: 'center' }}>{message}</div>}

            <form onSubmit={handleSubmit}>
                {!otpRequired ? (
                    <>
                        <div style={{ marginBottom: '15px' }}>
                            <label htmlFor="emailLogin" style={{ display: 'block', marginBottom: '5px' }}>Email:</label>
                            <input
                                id="emailLogin"
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                                style={{ width: 'calc(100% - 22px)', padding: '10px', borderRadius: '4px', border: '1px solid #ccc' }}
                            />
                        </div>
                        <div style={{ marginBottom: '15px' }}>
                            <label htmlFor="passwordLogin" style={{ display: 'block', marginBottom: '5px' }}>Password:</label>
                            <input
                                id="passwordLogin"
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                style={{ width: 'calc(100% - 22px)', padding: '10px', borderRadius: '4px', border: '1px solid #ccc' }}
                            />
                        </div>
                    </>
                ) : (
                    <div style={{ marginBottom: '15px' }}>
                        <label htmlFor="otpLogin" style={{ display: 'block', marginBottom: '5px' }}>Enter OTP Code (check your authenticator app):</label>
                        <input
                            id="otpLogin"
                            type="text"
                            maxLength="6"
                            value={otp}
                            onChange={(e) => setOtp(e.target.value)}
                            required
                            style={{ width: 'calc(100% - 22px)', padding: '10px', borderRadius: '4px', border: '1px solid #ccc', textAlign: 'center', fontSize: '1.2em' }}
                        />
                    </div>
                )}

                <button type="submit" style={{  width: '100%', padding: '12px', backgroundColor: '#4CAF50', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '1.1em' }}>
                    {otpRequired ? 'Verify OTP and Login' : 'Login'}
                </button>
            </form>

            <div style={{ marginTop: '20px', textAlign: 'center' }}>
                Don't have an account?{' '}
                <button onClick={() => navigate('/register')} style={{ background: 'none', border: 'none', color: '#2196F3', fontWeight: 'bold', cursor: 'pointer', padding: '0', fontSize: '1em' }}>
                    Register Here
                </button>
            </div>
        </div>
    );
}

export default LoginPage;
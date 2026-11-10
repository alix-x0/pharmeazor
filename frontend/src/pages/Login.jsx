import { useState } from "react";
import api from "@/api/api";
import { ACCESS_TOKEN, REFRESH_TOKEN } from "@/constants";
import { useNavigate, Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import Threads from "@/components/ui/Threads";

function Login() {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [errors, setErrors] = useState({});
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();

        let EmptyErrors = {};
        if (!username.trim()) EmptyErrors.username = "Email is required";
        if (!password) EmptyErrors.password = "Password is required";

        if (Object.keys(EmptyErrors).length > 0) {
            setErrors(EmptyErrors);
            return;
        }

        setErrors({});
        setLoading(true);
        try {
            const res = await api.post("/auth/login/", { username, password });
            localStorage.setItem(ACCESS_TOKEN, res.data.access);
            localStorage.setItem(REFRESH_TOKEN, res.data.refresh);
            navigate("/");
        } catch (error) {
            alert("Login failed. Please check your credentials.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#EFF6FF] dark:bg-zinc-950 w-full flex items-center justify-center p-4 md:p-6 relative overflow-hidden font-sans">
            {/* ─── Background Threads ─── */}
            <div className="absolute inset-0 z-0 pointer-events-none opacity-40">
                <Threads
                    color={[0.4, 0.72, 0.94]}
                    amplitude={0.8}
                    distance={0.1}
                    enableMouseInteraction
                />
            </div>

            <div className="relative z-10 w-full max-w-[850px] bg-white rounded-[24px] flex flex-col md:flex-row overflow-hidden p-2 min-h-[500px] md:h-[550px] gap-3 md:gap-4 shadow-2xl">
                
                {/* Left Side - Image & Quote */}
                <div className="hidden md:flex md:w-[50%] relative rounded-[18px] overflow-hidden">
                    <img 
                        src="https://images.unsplash.com/photo-1576765608535-5f04d1e3f289?q=80&w=2069&auto=format&fit=crop" 
                        alt="Medical Professional comforting a patient" 
                        className="absolute inset-0 w-full h-full object-cover"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#061225]/90 via-[#061225]/30 to-transparent" />
                    
                    <div className="absolute bottom-0 left-0 right-0 p-6 text-white flex flex-col justify-end">
                        <h2 className="text-[20px] md:text-[22px] font-semibold leading-[1.3] mb-4 tracking-tight font-sans">
                            "Medora's proactive alerts are a lifesaver. Our platform prevents dangerous drug accidents and costly hospitalizations before they happen."
                        </h2>
                        
                        <div className="mb-3">
                            <p className="font-semibold text-sm">Dr. Zoubeida Belbacha</p>
                            <p className="text-white/80 text-[11px]">Chief Medical Officer</p>
                        </div>
                        
                        <div className="flex gap-2 mt-1">
                            <button className="w-8 h-8 rounded-full border border-white/20 flex items-center justify-center backdrop-blur-sm hover:bg-white/15 transition-colors">
                                <ChevronLeft className="w-3.5 h-3.5 text-white/80" strokeWidth={1.5} />
                            </button>
                            <button className="w-8 h-8 rounded-full border border-white/20 flex items-center justify-center backdrop-blur-sm hover:bg-white/15 transition-colors">
                                <ChevronRight className="w-3.5 h-3.5 text-white/80" strokeWidth={1.5} />
                            </button>
                        </div>
                    </div>
                </div>

                {/* Right Side - Login Form */}
                <div className="w-full md:w-[50%] flex flex-col pt-5 pb-5 px-4 md:px-6 md:pr-8">
                    <span className="text-lg font-semibold tracking-tight text-sky-950 font-sans">
                        Medora.
                    </span>

                    <div className="flex-1 flex flex-col justify-center max-w-[360px] mx-auto w-full">
                        {/* Back Button */}
                        <button onClick={() => navigate(-1)} className="w-7 h-7 rounded-full border border-slate-200 flex items-center justify-center mb-4 hover:bg-blue-50 transition-colors self-start">
                            <ChevronLeft className="w-3.5 h-3.5 text-blue-600" />
                        </button>

                        <h1 className="text-[22px] font-semibold text-sky-950 mb-1.5 tracking-tighter font-sans">Let's join with us</h1>
                        <p className="text-slate-500 text-[13px] mb-5 leading-relaxed font-light font-sans">
                            You can sign in or join with us if you're new to Medora.
                        </p>

                        {/* Tabs (Removed since only standard login is supported) */}

                        <form onSubmit={handleSubmit} className="space-y-3.5">
                            <div className="space-y-1">
                                <label className="text-[11px] font-semibold text-sky-950 ml-1">Email address</label>
                                <div className="relative">
                                    <input
                                        type="email"
                                        placeholder="Enter your email"
                                        value={username}
                                        onChange={(e) => { setUsername(e.target.value); setErrors(prev => ({ ...prev, username: null })) }}
                                        className="w-full h-[42px] px-3.5 rounded-[12px] border border-slate-200 focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20 bg-white transition-all text-[13px] font-medium placeholder:text-slate-400 font-sans"
                                    />
                                </div>
                                {errors.username && <p className="text-[10px] text-red-500 ml-1">{errors.username}</p>}
                            </div>

                            <div className="space-y-1">
                                <label className="text-[11px] font-semibold text-sky-950 ml-1">Password</label>
                                <div className="relative">
                                    <input
                                        type="password"
                                        placeholder="••••••••"
                                        value={password}
                                        onChange={(e) => { setPassword(e.target.value); setErrors(prev => ({ ...prev, password: null })) }}
                                        className="w-full h-[42px] px-3.5 rounded-[12px] border border-slate-200 focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20 bg-white transition-all text-[13px] font-medium placeholder:text-slate-400 font-sans"
                                    />
                                </div>
                                {errors.password && <p className="text-[10px] text-red-500 ml-1">{errors.password}</p>}
                            </div>

                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full h-[42px] bg-[#061225] hover:bg-[#0a1d3a] text-white text-[13px] font-medium rounded-[12px] shadow-md transition-all mt-4 flex items-center justify-center font-sans active:scale-[0.98]"
                            >
                                {loading ? (
                                    <div className="flex items-center gap-2">
                                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                        <span>Logging in...</span>
                                    </div>
                                ) : (
                                    "Login"
                                )}
                            </button>
                        </form>
                    </div>

                    <div className="mt-auto pt-4 flex justify-center md:justify-start">
                        <p className="text-[12px] font-medium text-slate-500">
                            Don't have an account?{" "}
                            <Link to="/register" className="font-semibold text-blue-600 hover:text-blue-700 transition-colors">
                                Sign up
                            </Link>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default Login;

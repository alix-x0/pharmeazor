import { useState, useEffect } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import {
    Menu, X, User, Settings, LogOut,
    ChevronDown, LayoutDashboard, Bell, Sun, Moon, Globe
} from "lucide-react";
import { useTheme } from "@/components/theme-provider";
import { useLanguage } from "../../contexts/LanguageContext";
import api from "@/api/api";
import { ACCESS_TOKEN } from "@/constants";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";

export default function Navbar() {
    const [menuOpen, setMenuOpen] = useState(false);
    const [userInfo, setUserInfo] = useState(null);
    const [scrolled, setScrolled] = useState(false);
    const [isLangMenuOpen, setIsLangMenuOpen] = useState(false);
    const navigate = useNavigate();
    const location = useLocation();
    const { theme, setTheme } = useTheme();
    const { t, language, changeLanguage } = useLanguage();

    useEffect(() => {
        const handleScroll = () => setScrolled(window.scrollY > 20);
        window.addEventListener("scroll", handleScroll);
        return () => window.removeEventListener("scroll", handleScroll);
    }, []);

    useEffect(() => {
        const fetchProfile = async () => {
            try {
                const token = localStorage.getItem(ACCESS_TOKEN);
                if (token) {
                    const res = await api.get('/auth/profile/');
                    setUserInfo(res.data);
                } else {
                    setUserInfo(null);
                }
            } catch (error) {
                console.error("Failed to fetch profile:", error);
                setUserInfo(null);
            }
        };
        fetchProfile();
    }, [location.pathname]);

    const handleLogout = () => {
        localStorage.clear();
        setUserInfo(null);
        navigate("/login");
    };

    const navLinks = [
        { name: t("home"), path: "/" },
        { name: t("interactions"), path: "/interactions" },
        { name: t("about"), path: "/about" },
    ];

    const isHome = location.pathname === "/";
    const transparentMode = isHome && !scrolled;

    return (
        <nav className={`fixed top-0 left-0 right-0 z-[100] transition-all duration-300 ${
            transparentMode 
                ? "bg-transparent pt-4 pb-2" 
                : "bg-white/95 backdrop-blur-md border-b border-slate-100 shadow-sm"
        }`}>
            <div className={`max-w-7xl mx-auto px-6 flex items-center justify-between transition-all duration-300 ${transparentMode ? "h-14" : "h-16"}`}>
                <Link to="/" className="flex items-center gap-0.5 hover:opacity-80 transition-opacity">
                    <span className={`text-2xl font-bold tracking-tighter transition-colors ${transparentMode ? "text-white drop-shadow-md" : "text-slate-900 dark:text-white"}`}>Medora</span>
                    <span className={`text-3xl leading-none -mt-1 transition-colors ${transparentMode ? "text-white drop-shadow-md" : "text-slate-900 dark:text-white"}`}>.</span>
                </Link>

                {/* Desktop Menu */}
                <div className="hidden md:flex items-center gap-3">
                    {navLinks.map((link) => (
                        <Link
                            key={link.path}
                            to={link.path}
                            className={
                                transparentMode
                                    ? `px-4 py-2 rounded-[10px] font-medium text-[13.5px] transition-all bg-black/20 backdrop-blur-md border border-white/10 text-white hover:bg-white/10 shadow-lg`
                                    : `px-4 py-2 rounded-[10px] font-medium text-[13.5px] transition-all ${location.pathname === link.path ? "text-slate-900 bg-slate-100 dark:text-white dark:bg-zinc-800" : "text-slate-600 hover:text-slate-900 hover:bg-slate-50 dark:text-slate-400 dark:hover:text-white dark:hover:bg-zinc-800/50"}`
                            }
                        >
                            {link.name}
                        </Link>
                    ))}

                    <div className={`h-4 w-px mx-1 transition-colors ${transparentMode ? "bg-white/20" : "bg-slate-200"}`}></div>

                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                        className={
                            transparentMode
                                ? "rounded-[10px] w-9 h-9 text-white bg-black/20 backdrop-blur-md border border-white/10 hover:bg-white/10 transition-all shadow-lg"
                                : "rounded-[10px] w-9 h-9 text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-zinc-800 transition-all shadow-none"
                        }
                    >
                        {theme === "dark" ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
                        <span className="sr-only">Toggle theme</span>
                    </Button>

                    <div className={`h-4 w-px mx-1 transition-colors ${transparentMode ? "bg-white/20" : "bg-slate-200"}`}></div>

                    {/* Language Switcher */}
                    <div className="relative">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setIsLangMenuOpen(!isLangMenuOpen)}
                            className={
                                transparentMode
                                    ? "rounded-[10px] h-9 px-2.5 text-[11px] font-bold text-white bg-black/20 backdrop-blur-md border border-white/10 hover:bg-white/10 transition-all shadow-lg uppercase tracking-widest"
                                    : "rounded-[10px] h-9 px-2.5 text-[11px] font-bold text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-zinc-800 transition-all uppercase tracking-widest"
                            }
                        >
                            <Globe className="w-3.5 h-3.5 mr-1.5" />
                            {language}
                        </Button>
                        {isLangMenuOpen && (
                            <div className={`absolute right-0 mt-2 w-28 rounded-xl shadow-2xl border py-1.5 z-50 overflow-hidden ${transparentMode ? "bg-black/60 backdrop-blur-xl border-white/10" : "bg-white border-slate-100"}`}>
                                <button onClick={() => { changeLanguage('en'); setIsLangMenuOpen(false); }} className={`w-full px-4 py-2 text-[10px] font-bold text-left hover:bg-blue-50/50 uppercase tracking-widest ${transparentMode ? "text-white hover:bg-white/10" : "text-slate-600 hover:text-blue-600"}`}>EN - English</button>
                                <button onClick={() => { changeLanguage('fr'); setIsLangMenuOpen(false); }} className={`w-full px-4 py-2 text-[10px] font-bold text-left hover:bg-blue-50/50 uppercase tracking-widest ${transparentMode ? "text-white hover:bg-white/10" : "text-slate-600 hover:text-blue-600"}`}>FR - Français</button>
                                <button onClick={() => { changeLanguage('ar'); setIsLangMenuOpen(false); }} className={`w-full px-4 py-2 text-[10px] font-bold text-right hover:bg-blue-50/50 uppercase tracking-widest font-arabic ${transparentMode ? "text-white hover:bg-white/10" : "text-slate-600 hover:text-blue-600"}`}>AR - العربية</button>
                            </div>
                        )}
                    </div>

                    <div className={`h-4 w-px mx-1 transition-colors ${transparentMode ? "bg-white/20" : "bg-slate-200"}`}></div>

                    {userInfo ? (
                        <DropdownMenu modal={false}>
                            <DropdownMenuTrigger asChild>
                                <Button variant="ghost" className={`relative h-10 w-auto flex items-center gap-2.5 pl-1 pr-3.5 rounded-full group transition-all duration-200 ${
                                    transparentMode 
                                    ? "bg-black/20 backdrop-blur-md border border-white/10 hover:bg-white/10 hover:text-white data-[state=open]:bg-white/10 data-[state=open]:text-white shadow-lg text-white"
                                    : "hover:bg-slate-100 data-[state=open]:bg-slate-100 dark:hover:bg-zinc-800 dark:data-[state=open]:bg-zinc-800"
                                }`}>
                                    <Avatar className={`h-8 w-8 shadow-sm transition-all ${transparentMode ? "border-none" : "border border-white ring-1 ring-slate-100 group-hover:ring-slate-200 dark:border-zinc-900 dark:ring-zinc-800 dark:group-hover:ring-zinc-700"}`}>
                                        {userInfo.profile_picture && (
                                            <img src={userInfo.profile_picture} alt={userInfo.username} className="h-full w-full object-cover" />
                                        )}
                                        <AvatarFallback className={`${transparentMode ? "bg-white/20 text-white" : "bg-slate-900 text-white dark:bg-white dark:text-zinc-900"} text-[10px] font-medium uppercase backdrop-blur-sm`}>
                                            {userInfo.username?.charAt(0).toUpperCase() || 'A'}
                                        </AvatarFallback>
                                    </Avatar>
                                    <div className="text-left hidden lg:block pr-1">
                                        <p className={`text-xs font-semibold leading-none mb-1 ${transparentMode ? "text-white" : "text-slate-900 dark:text-white"}`}>{userInfo.username}</p>
                                        <p className={`text-[10px] font-medium ${transparentMode ? "text-white/70" : "text-slate-500 dark:text-slate-400"}`}>
                                            {userInfo.role?.charAt(0).toUpperCase() + userInfo.role?.slice(1).toLowerCase().replace('_', ' ')}
                                        </p>
                                    </div>
                                    <ChevronDown className={`h-3 w-3 transition-colors ${transparentMode ? "text-white/60 group-hover:text-white" : "text-slate-400 group-hover:text-slate-900 dark:group-hover:text-white"}`} />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent 
                                className={`w-56 mt-2 rounded-2xl p-2 shadow-2xl transition-colors ${
                                    transparentMode
                                        ? "border-white/10 bg-black/60 backdrop-blur-xl text-white"
                                        : "border-slate-100 bg-white text-slate-900"
                                }`} 
                                align="end" 
                                forceMount
                            >
                                <DropdownMenuLabel className="font-normal px-2.5 py-2.5">
                                    <div className="flex flex-col space-y-0.5">
                                        <p className={`text-[13.5px] font-semibold tracking-tight leading-none ${transparentMode ? "text-white" : "text-slate-900 dark:text-white"}`}>{userInfo.username}</p>
                                        <p className={`text-[11px] font-medium truncate ${transparentMode ? "text-white/70" : "text-slate-500 dark:text-slate-400"}`}>{userInfo.email}</p>
                                    </div>
                                </DropdownMenuLabel>
                                <DropdownMenuSeparator className={transparentMode ? "bg-white/10" : "bg-slate-100 dark:bg-zinc-800"} />
                                {(userInfo.role?.toLowerCase() === "pharmacist" || userInfo.role?.toLowerCase() === "admin") && (
                                    <DropdownMenuItem asChild className={transparentMode ? "focus:bg-white/20 focus:text-white" : "focus:bg-slate-50 dark:focus:bg-zinc-800/50"}>
                                        <Link to="/dashboard" className={`cursor-pointer font-medium text-[13px] p-2 rounded-[10px] flex items-center transition-colors w-full ${
                                            transparentMode ? "text-white hover:bg-white/20" : "text-slate-700 hover:bg-slate-50 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-zinc-800/50 dark:hover:text-white"
                                        }`}>
                                            <LayoutDashboard className={`mr-2.5 h-[15px] w-[15px] ${transparentMode ? "text-white/80" : "text-slate-900 dark:text-white"}`} />
                                            Dashboard
                                        </Link>
                                    </DropdownMenuItem>
                                )}
                                <DropdownMenuItem asChild className={transparentMode ? "focus:bg-white/20 focus:text-white" : "focus:bg-slate-50 dark:focus:bg-zinc-800/50"}>
                                    <Link to="/profile" className={`cursor-pointer font-medium text-[13px] p-2 rounded-[10px] flex items-center transition-colors w-full ${
                                        transparentMode ? "text-white hover:bg-white/20" : "text-slate-700 hover:bg-slate-50 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-zinc-800/50 dark:hover:text-white"
                                    }`}>
                                        <User className={`mr-2.5 h-[15px] w-[15px] ${transparentMode ? "text-white/80" : "text-slate-900 dark:text-white"}`} />
                                        View Profile
                                    </Link>
                                </DropdownMenuItem>
                                <DropdownMenuItem asChild className={transparentMode ? "focus:bg-white/20 focus:text-white" : "focus:bg-slate-50 dark:focus:bg-zinc-800/50"}>
                                    <Link to="/settings" className={`cursor-pointer font-medium text-[13px] p-2 rounded-[10px] flex items-center transition-colors w-full ${
                                        transparentMode ? "text-white hover:bg-white/20" : "text-slate-700 hover:bg-slate-50 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-zinc-800/50 dark:hover:text-white"
                                    }`}>
                                        <Settings className={`mr-2.5 h-[15px] w-[15px] ${transparentMode ? "text-white/80" : "text-slate-900 dark:text-white"}`} />
                                        Settings
                                    </Link>
                                </DropdownMenuItem>
                                <DropdownMenuSeparator className={transparentMode ? "bg-white/10" : "bg-slate-100 dark:bg-zinc-800"} />
                                <DropdownMenuItem 
                                    onClick={handleLogout} 
                                    className={`cursor-pointer font-semibold text-[13px] p-2 rounded-[10px] flex items-center transition-colors w-full ${
                                        transparentMode 
                                            ? "text-red-400 hover:bg-red-400/20 hover:text-red-300 focus:bg-red-400/20 focus:text-red-300" 
                                            : "text-red-600 hover:bg-red-50 focus:bg-red-50 focus:text-red-700"
                                    }`}
                                >
                                    <LogOut className="mr-2.5 h-[15px] w-[15px]" />
                                    Logout
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                    ) : (
                        <div className="flex items-center gap-3">
                            <Link to="/login">
                                <Button variant="ghost" className={
                                    transparentMode
                                    ? "text-[13.5px] font-medium text-white bg-black/20 backdrop-blur-md border border-white/10 hover:bg-white/10 transition-colors px-5 h-9 shadow-lg rounded-[12px]"
                                    : "text-[13.5px] font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-zinc-800 transition-colors px-5 h-9 shadow-none rounded-[12px]"
                                }>
                                    Log In
                                </Button>
                            </Link>
                            <Link to="/register">
                                <Button className={
                                    transparentMode
                                    ? "bg-white hover:bg-white/90 text-black text-[13px] font-medium rounded-[12px] px-6 h-9 shadow-lg active:scale-[0.98] transition-all border-none"
                                    : "bg-slate-900 hover:bg-slate-800 dark:bg-white dark:text-zinc-900 dark:hover:bg-slate-200 text-white text-[13.5px] font-medium rounded-[12px] px-6 h-9 shadow-sm active:scale-[0.98] transition-all border-none"
                                }>
                                    Register
                                </Button>
                            </Link>
                        </div>
                    )}
                </div>

                {/* Mobile Menu Button */}
                <button
                    className={`md:hidden p-2 rounded-lg transition-colors ${transparentMode ? "text-white hover:bg-white/20 bg-black/40 backdrop-blur-md border border-white/20 shadow-lg" : "text-slate-600 hover:bg-slate-100"}`}
                    onClick={() => setMenuOpen(!menuOpen)}
                >
                    {menuOpen ? <X size={24} /> : <Menu size={24} />}
                </button>
            </div>

            {/* Mobile Menu */}
            {menuOpen && (
                <div className="md:hidden absolute top-[100%] left-0 right-0 bg-white border-b border-slate-100 p-6 space-y-4 shadow-xl animate-in fade-in slide-in-from-top-4">
                    {navLinks.map((link) => (
                        <Link
                            key={link.path}
                            to={link.path}
                            className={`block py-3.5 px-4 rounded-xl text-[13px] font-bold transition-all ${location.pathname === link.path ? "bg-primary/10 text-primary" : "text-slate-600 hover:bg-slate-50"
                                }`}
                            onClick={() => setMenuOpen(false)}
                        >
                            {link.name}
                        </Link>
                    ))}

                    <div className="h-px bg-slate-100 my-4"></div>

                    {userInfo ? (
                        <div className="space-y-4 px-2">
                            <div className="flex items-center gap-4 py-2">
                                <Avatar className="h-10 w-10">
                                    {userInfo.profile_picture && (
                                        <img src={userInfo.profile_picture} alt={userInfo.username} className="h-full w-full object-cover" />
                                    )}
                                    <AvatarFallback className="bg-primary text-white font-medium">{userInfo.username?.charAt(0).toUpperCase() || 'A'}</AvatarFallback>
                                </Avatar>
                                <div>
                                    <p className="text-sm font-semibold text-slate-900">{userInfo.username}</p>
                                    <p className="text-xs text-primary font-medium">{userInfo.role?.replace('_', ' ')}</p>
                                </div>
                            </div>
                            {(userInfo.role?.toLowerCase() === "pharmacist" || userInfo.role?.toLowerCase() === "admin") && (
                                <Link to="/dashboard" className="block py-3.5 px-2 text-[13px] font-bold text-primary" onClick={() => setMenuOpen(false)}>Dashboard</Link>
                            )}
                            <button onClick={handleLogout} className="block w-full text-left py-3.5 px-2 text-[13px] font-bold text-red-600">Logout</button>
                        </div>
                    ) : (
                        <div className="space-y-3 pt-2">
                            <Link to="/login" className="block w-full text-center py-3.5 border border-slate-100 hover:bg-slate-50 rounded-xl font-medium text-[13px] text-slate-900 transition-all" onClick={() => setMenuOpen(false)}>Log In</Link>
                            <Link to="/register" className="block w-full text-center py-3.5 bg-primary hover:bg-primary/95 rounded-xl font-bold text-[13px] text-white shadow-xl shadow-primary/10 transition-all" onClick={() => setMenuOpen(false)}>Register</Link>
                        </div>
                    )}
                </div>
            )}
        </nav>
    );
}

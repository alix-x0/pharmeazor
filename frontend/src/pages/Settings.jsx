import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/api/api";
import { ACCESS_TOKEN } from "@/constants";
import {
    User, Mail, Phone, Shield, Bell, Lock, Loader2, Save, Key, Smartphone, Settings as SettingsIcon
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

export default function Settings() {
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const navigate = useNavigate();

    const [activeTab, setActiveTab] = useState("profile");

    // Form state
    const [formData, setFormData] = useState({
        username: "",
        email: "",
        phone: "",
        bio: "",
    });

    const [notifications, setNotifications] = useState({
        marketing: false,
        applicationUpdates: true,
        securityAlerts: true,
    });

    useEffect(() => {
        const fetchProfile = async () => {
            try {
                const token = localStorage.getItem(ACCESS_TOKEN);
                if (token) {
                    const res = await api.get('/auth/profile/');
                    setProfile(res.data);
                    setFormData({
                        username: res.data.username || "",
                        email: res.data.email || "",
                        phone: res.data.phone || "",
                        bio: res.data.bio || "",
                    });
                } else {
                    navigate('/login');
                }
            } catch (error) {
                console.error("Error fetching profile:", error);
            } finally {
                setLoading(false);
            }
        };
        fetchProfile();
    }, [navigate]);

    const handleSave = async () => {
        setSaving(true);
        try {
            await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate delay
            alert("Settings saved successfully!");
        } catch (error) {
            alert("Failed to save settings.");
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="flex h-[60vh] items-center justify-center bg-slate-50">
                <div className="flex flex-col items-center gap-4">
                    <Loader2 className="w-8 h-8 text-primary animate-spin" />
                    <p className="text-sm font-medium text-slate-500">Loading settings...</p>
                </div>
            </div>
        );
    }

    const CustomToggle = ({ checked, onChange }) => (
        <label className="relative inline-flex items-center cursor-pointer">
            <input type="checkbox" className="sr-only peer" checked={checked} onChange={onChange} />
            <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer dark:bg-slate-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-slate-600 peer-checked:bg-primary"></div>
        </label>
    );

    return (
        <div className="bg-slate-50 min-h-screen py-16 px-4 md:px-6">
            <div className="max-w-4xl mx-auto">
                <div className="relative overflow-hidden bg-white rounded-2xl border border-slate-200 p-8 mb-8 shadow-sm">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3"></div>
                    <div className="relative z-10 flex items-center gap-5">
                        <div className="w-14 h-14 bg-primary/10 rounded-xl flex items-center justify-center text-primary shadow-inner border border-primary/20">
                            <SettingsIcon className="w-7 h-7" />
                        </div>
                        <div>
                            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Account Settings</h1>
                            <p className="text-slate-500 mt-1 font-medium">Manage your account preferences, profile details, and security.</p>
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
                    {/* Settings Sidebar */}
                    <div className="md:col-span-1 space-y-2">
                        <Button 
                            variant={activeTab === "profile" ? "secondary" : "ghost"} 
                            className={`w-full justify-start font-medium ${activeTab === "profile" ? "bg-white shadow-sm border border-slate-200 text-primary" : "text-slate-500 hover:text-slate-900"}`}
                            onClick={() => setActiveTab("profile")}
                        >
                            <User className="mr-2 h-4 w-4" /> Profile
                        </Button>
                        <Button 
                            variant={activeTab === "notifications" ? "secondary" : "ghost"} 
                            className={`w-full justify-start font-medium ${activeTab === "notifications" ? "bg-white shadow-sm border border-slate-200 text-primary" : "text-slate-500 hover:text-slate-900"}`}
                            onClick={() => setActiveTab("notifications")}
                        >
                            <Bell className="mr-2 h-4 w-4" /> Notifications
                        </Button>
                        <Button 
                            variant={activeTab === "security" ? "secondary" : "ghost"} 
                            className={`w-full justify-start font-medium ${activeTab === "security" ? "bg-white shadow-sm border border-slate-200 text-primary" : "text-slate-500 hover:text-slate-900"}`}
                            onClick={() => setActiveTab("security")}
                        >
                            <Shield className="mr-2 h-4 w-4" /> Security
                        </Button>
                    </div>

                    {/* Settings Content */}
                    <div className="md:col-span-3 space-y-6">
                        {activeTab === "profile" && (
                            <Card className="border-slate-200 shadow-sm rounded-2xl overflow-hidden bg-white">
                                <CardHeader className="border-b border-slate-100 pb-5 pt-6 px-8">
                                    <CardTitle className="text-xl font-bold text-slate-800">Public Profile</CardTitle>
                                    <CardDescription>This information will be displayed publicly.</CardDescription>
                                </CardHeader>
                                <CardContent className="p-8 space-y-8">
                                    <div className="flex items-center gap-6">
                                        <Avatar className="w-20 h-20 border border-slate-200 shadow-sm">
                                            {profile?.profile_picture && <AvatarImage src={profile.profile_picture} />}
                                            <AvatarFallback className="bg-primary/10 text-primary font-medium text-xl">
                                                {formData.username?.charAt(0).toUpperCase() || 'U'}
                                            </AvatarFallback>
                                        </Avatar>
                                        <Button variant="outline" size="sm" className="font-medium h-9">
                                            Change Avatar
                                        </Button>
                                    </div>

                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div className="space-y-2">
                                            <Label htmlFor="username">Username</Label>
                                            <div className="relative">
                                                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                                <Input 
                                                    id="username" 
                                                    value={formData.username}
                                                    onChange={e => setFormData({...formData, username: e.target.value})}
                                                    className="pl-9 bg-slate-50 border-slate-200" 
                                                />
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="email">Email Address</Label>
                                            <div className="relative">
                                                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                                <Input 
                                                    id="email" 
                                                    type="email"
                                                    value={formData.email}
                                                    onChange={e => setFormData({...formData, email: e.target.value})}
                                                    className="pl-9 bg-slate-50 border-slate-200" 
                                                    readOnly
                                                />
                                            </div>
                                        </div>
                                        <div className="space-y-2 md:col-span-2">
                                            <Label htmlFor="phone">Phone Number</Label>
                                            <div className="relative">
                                                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                                <Input 
                                                    id="phone" 
                                                    value={formData.phone}
                                                    onChange={e => setFormData({...formData, phone: e.target.value})}
                                                    className="pl-9 bg-slate-50 border-slate-200" 
                                                    placeholder="+213 555 0000"
                                                />
                                            </div>
                                        </div>
                                        <div className="space-y-2 md:col-span-2">
                                            <Label htmlFor="bio">Biography</Label>
                                            <textarea
                                                id="bio"
                                                value={formData.bio}
                                                onChange={e => setFormData({...formData, bio: e.target.value})}
                                                className="flex min-h-[100px] w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm ring-offset-white placeholder:text-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                                                placeholder="Write a few sentences about yourself..."
                                            />
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {activeTab === "notifications" && (
                            <Card className="border-slate-200 shadow-sm rounded-2xl overflow-hidden bg-white">
                                <CardHeader className="border-b border-slate-100 pb-5 pt-6 px-8">
                                    <CardTitle className="text-xl font-bold text-slate-800">Notification Preferences</CardTitle>
                                    <CardDescription>Choose what updates you want to receive.</CardDescription>
                                </CardHeader>
                                <CardContent className="p-8 space-y-6">
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label className="text-base font-semibold">Application Updates</Label>
                                            <p className="text-sm text-slate-500">Receive emails when an application status changes.</p>
                                        </div>
                                        <CustomToggle 
                                            checked={notifications.applicationUpdates} 
                                            onChange={() => setNotifications({...notifications, applicationUpdates: !notifications.applicationUpdates})} 
                                        />
                                    </div>
                                    <Separator className="bg-slate-100" />
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label className="text-base font-semibold">Security Alerts</Label>
                                            <p className="text-sm text-slate-500">Get notified about new sign-ins or password changes.</p>
                                        </div>
                                        <CustomToggle 
                                            checked={notifications.securityAlerts} 
                                            onChange={() => setNotifications({...notifications, securityAlerts: !notifications.securityAlerts})} 
                                        />
                                    </div>
                                    <Separator className="bg-slate-100" />
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label className="text-base font-semibold">Marketing & Promotions</Label>
                                            <p className="text-sm text-slate-500">Receive occasional emails about new features.</p>
                                        </div>
                                        <CustomToggle 
                                            checked={notifications.marketing} 
                                            onChange={() => setNotifications({...notifications, marketing: !notifications.marketing})} 
                                        />
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {activeTab === "security" && (
                            <Card className="border-slate-200 shadow-sm rounded-2xl overflow-hidden bg-white">
                                <CardHeader className="border-b border-slate-100 pb-5 pt-6 px-8">
                                    <CardTitle className="text-xl font-bold text-slate-800">Security Settings</CardTitle>
                                    <CardDescription>Manage your password and security keys.</CardDescription>
                                </CardHeader>
                                <CardContent className="p-8 space-y-8">
                                    <div className="space-y-4">
                                        <h3 className="text-base font-semibold flex items-center gap-2">
                                            <Key className="w-4 h-4 text-primary" /> Change Password
                                        </h3>
                                        <div className="grid gap-4">
                                            <div className="space-y-2">
                                                <Label htmlFor="current_password">Current Password</Label>
                                                <div className="relative">
                                                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                                    <Input id="current_password" type="password" className="pl-9 bg-slate-50 border-slate-200" />
                                                </div>
                                            </div>
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                <div className="space-y-2">
                                                    <Label htmlFor="new_password">New Password</Label>
                                                    <Input id="new_password" type="password" className="bg-slate-50 border-slate-200" />
                                                </div>
                                                <div className="space-y-2">
                                                    <Label htmlFor="confirm_password">Confirm Password</Label>
                                                    <Input id="confirm_password" type="password" className="bg-slate-50 border-slate-200" />
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <Separator className="bg-slate-100" />
                                    <div className="space-y-4">
                                        <div className="flex items-center justify-between">
                                            <div>
                                                <h3 className="text-base font-semibold flex items-center gap-2">
                                                    <Smartphone className="w-4 h-4 text-primary" /> Two-Factor Authentication
                                                </h3>
                                                <p className="text-sm text-slate-500 mt-1">Add an extra layer of security to your account.</p>
                                            </div>
                                            <Button variant="outline" className="font-medium">Enable 2FA</Button>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        <div className="flex justify-end gap-4">
                            <Button variant="outline" className="h-11 px-6 font-medium">Cancel</Button>
                            <Button onClick={handleSave} disabled={saving} className="h-11 px-8 font-semibold shadow-sm">
                                {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                                Save Changes
                            </Button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

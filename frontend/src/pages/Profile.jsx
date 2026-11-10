import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/api/api";
import { ACCESS_TOKEN } from "@/constants";
import {
    Mail, Phone, Shield, Calendar, Loader2, Settings, CheckCircle2,
    Pill, Search, Plus, Trash2, Upload, FileImage, X, MapPin,
    Heart, Activity, AlertTriangle, Clock, User as UserIcon
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useLanguage } from "../contexts/LanguageContext";

export default function Profile() {
    const { t } = useLanguage();
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();
    const [savedMeds, setSavedMeds] = useState([]);
    const [medSearchTerm, setMedSearchTerm] = useState("");
    const [medSuggestions, setMedSuggestions] = useState([]);
    const [loadingMeds, setLoadingMeds] = useState(false);
    const [addingMed, setAddingMed] = useState(false);
    const [uploadedFile, setUploadedFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [dragOver, setDragOver] = useState(false);
    const fileInputRef = useRef(null);

    // Editable medical/contact info (stored in localStorage for now)
    const [medicalInfo, setMedicalInfo] = useState(() => {
        const saved = localStorage.getItem('Medora_medical_info');
        return saved ? JSON.parse(saved) : { blood_type: '', allergies: '', conditions: '', emergency_contact: '' };
    });
    const [contactInfo, setContactInfo] = useState(() => {
        const saved = localStorage.getItem('Medora_contact_info');
        return saved ? JSON.parse(saved) : { phone: '', wilaya: '', address: '' };
    });
    const [editingMedInfo, setEditingMedInfo] = useState(false);
    const [editingContact, setEditingContact] = useState(false);

    useEffect(() => {
        const fetchProfile = async () => {
            try {
                const token = localStorage.getItem(ACCESS_TOKEN);
                if (token) {
                    const res = await api.get('/auth/profile/');
                    setProfile(res.data);
                } else { navigate('/login'); }
            } catch (error) { console.error(error); }
            finally { setLoading(false); }
        };
        fetchProfile();
        fetchSavedMeds();
    }, [navigate]);

    const fetchSavedMeds = async () => {
        setLoadingMeds(true);
        try {
            const res = await api.get('/medication-profile/');
            const data = res.data;
            setSavedMeds(Array.isArray(data) ? data : (data.results || []));
        } catch (e) { console.error(e); }
        finally { setLoadingMeds(false); }
    };

    useEffect(() => {
        if (medSearchTerm.length < 2) { setMedSuggestions([]); return; }
        const timer = setTimeout(async () => {
            try {
                const res = await api.get(`/drugs/?search=${medSearchTerm}`);
                const existing = savedMeds.map(m => m.drug?.registration_number);
                setMedSuggestions(res.data.results.filter(d => !existing.includes(d.registration_number)));
            } catch (e) { console.error(e); }
        }, 300);
        return () => clearTimeout(timer);
    }, [medSearchTerm, savedMeds]);

    const addMedToProfile = async (drug) => {
        setAddingMed(true);
        try {
            await api.post('/medication-profile/', { drug_id: drug.id });
            setMedSearchTerm(""); setMedSuggestions([]); fetchSavedMeds();
        } catch (e) { console.error(e); }
        finally { setAddingMed(false); }
    };

    const removeMed = async (id) => {
        try { await api.delete(`/medication-profile/${id}/`); setSavedMeds(savedMeds.filter(m => m.id !== id)); }
        catch (e) { console.error(e); }
    };

    const handleFileDrop = (e) => {
        e.preventDefault(); setDragOver(false);
        const file = e.dataTransfer?.files?.[0] || e.target?.files?.[0];
        if (file && (file.type.startsWith('image/') || file.type === 'application/pdf')) setUploadedFile(file);
    };

    const handleUploadScan = async () => {
        if (!uploadedFile) return;
        setUploading(true);
        try {
            const formData = new FormData();
            formData.append('file', uploadedFile);
            const res = await api.post('/medication-profile/scan/', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            const matches = res.data.matches || [];
            let addedCount = 0;
            const existingRegNums = savedMeds.map(m => m.drug?.registration_number);
            for (const match of matches) {
                if (match.match_score >= 80 && !existingRegNums.includes(match.drug.registration_number)) {
                    await api.post('/medication-profile/', { drug_id: match.drug.id });
                    addedCount++;
                    existingRegNums.push(match.drug.registration_number);
                }
            }
            alert(`Prescription scan complete. Extracted and saved ${addedCount} medications.`);
            fetchSavedMeds();
            setUploadedFile(null);
        } catch (error) {
            console.error("Scan failed:", error);
            alert("Failed to scan prescription. Please try again.");
        } finally {
            setUploading(false);
        }
    };

    const saveMedicalInfo = () => {
        localStorage.setItem('Medora_medical_info', JSON.stringify(medicalInfo));
        setEditingMedInfo(false);
    };

    const saveContactInfo = () => {
        localStorage.setItem('Medora_contact_info', JSON.stringify(contactInfo));
        setEditingContact(false);
    };

    if (loading) return (
        <div className="flex h-[60vh] items-center justify-center bg-slate-50">
            <div className="flex flex-col items-center gap-4">
                <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
                <p className="text-sm font-medium text-slate-500 font-light">{t('loading_profile')}</p>
            </div>
        </div>
    );

    if (!profile) return (
        <div className="min-h-[60vh] flex flex-col items-center justify-center bg-slate-50 text-center px-4">
            <p className="text-lg text-slate-500 mb-6 font-medium">Unable to load profile data.</p>
            <Button variant="default" onClick={() => navigate('/')}>Return Home</Button>
        </div>
    );

    return (
        <div className="bg-slate-50 min-h-screen py-16 px-4 md:px-6">
            <div className="max-w-5xl mx-auto">
                {/* Profile Header */}
                <div className="bg-[#061225] rounded-[24px] p-10 mb-8 shadow-xl shadow-blue-950/20 relative overflow-hidden group">
                    {/* Subtle decorative element */}
                    <div className="absolute top-0 right-0 -mr-16 -mt-16 w-64 h-64 bg-blue-600/10 rounded-full blur-3xl"></div>
                    
                    <div className="flex flex-col md:flex-row items-center gap-10 relative z-10">
                        <Avatar className="w-32 h-32 border-4 border-white/10 shadow-2xl ring-4 ring-white/5 flex items-center justify-center overflow-hidden">
                            {profile.profile_picture && <img src={profile.profile_picture} alt={profile.username} className="w-full h-full object-cover" />}
                            <AvatarFallback className="bg-blue-50 text-blue-600 font-bold text-4xl">{profile.username?.charAt(0).toUpperCase() || 'A'}</AvatarFallback>
                        </Avatar>
                        <div className="text-center md:text-left flex-grow space-y-2">
                            <h1 className="text-3xl font-bold text-white tracking-tighter leading-tight">{profile.first_name || profile.username} {profile.last_name || ''}</h1>
                            <p className="text-blue-400 mb-4 font-light text-lg">@{profile.username}</p>
                            <div className="flex flex-wrap justify-center md:justify-start gap-3 items-center">
                                <Badge className="bg-blue-600 text-white border-none rounded-full font-bold text-[10px] px-4 py-1.5 uppercase tracking-widest">{profile.role?.replace('_', ' ')}</Badge>
                                {profile.wilaya && <Badge variant="outline" className="rounded-full text-[10px] font-bold border-white/10 text-blue-100/60 gap-1 uppercase tracking-wider"><MapPin className="w-3.5 h-3.5" />{profile.wilaya}</Badge>}
                                {profile.age && <Badge variant="outline" className="rounded-full text-[10px] font-bold border-white/10 text-blue-100/60 uppercase tracking-wider">{profile.age} {t('yrs')}</Badge>}
                            </div>
                        </div>
                        <Button 
                            variant="outline" 
                            onClick={() => navigate('/settings')} 
                            className="rounded-2xl h-12 px-8 font-bold border-white/10 text-white bg-white/5 hover:bg-white/10 transition-all active:scale-95"
                        >
                            <Settings className="w-4 h-4" /> {t('settings')}
                        </Button>
                    </div>
                </div>

                {/* Stats Row */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                    {[
                        { label: "Saved Medications", value: savedMeds.length, icon: Pill, color: "emerald" },
                        { label: "Profile Status", value: "Active", icon: CheckCircle2, color: "blue" },
                        { label: "Risk Alerts", value: "0", icon: AlertTriangle, color: "amber" },
                        { label: "Last Check", value: "Today", icon: Clock, color: "slate" },
                    ].map((stat, i) => (
                        <div key={i} className="bg-white rounded-xl border border-slate-200 px-5 py-4 shadow-sm">
                            <div className="flex items-center gap-2 mb-2">
                                <stat.icon className={`w-4 h-4 text-${stat.color}-500`} />
                                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{stat.label}</span>
                            </div>
                            <p className="text-xl font-bold text-slate-900">{stat.value}</p>
                        </div>
                    ))}
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* Sidebar */}
                    <div className="space-y-6">
                        {/* Contact */}
                        <div className="bg-white border border-slate-200/60 shadow-sm rounded-[24px] overflow-hidden">
                            <div className="bg-slate-50/50 px-6 py-4 border-b border-slate-100/30 flex items-center justify-between">
                                <h3 className="text-[13px] font-medium text-slate-400/80">{t('contact')}</h3>
                                <button onClick={() => editingContact ? saveContactInfo() : setEditingContact(true)} className="text-[11px] font-bold text-blue-600 hover:underline">
                                    {editingContact ? t('save') : t('edit')}
                                </button>
                            </div>
                            <div className="px-6 py-6 space-y-5">
                                <div className="space-y-1">
                                    <div className="flex items-center gap-2 text-slate-400/80">
                                        <Mail className="w-3.5 h-3.5" />
                                        <span className="text-[10px] font-bold uppercase tracking-widest">{t('email_label')}</span>
                                    </div>
                                    <p className="text-sm font-semibold text-sky-950 pl-0.5 tracking-tight">{profile.email}</p>
                                </div>

                                <div className="space-y-1">
                                    <div className="flex items-center gap-2 text-slate-400/80">
                                        <Phone className="w-3.5 h-3.5" />
                                        <span className="text-[10px] font-bold uppercase tracking-widest">{t('phone_label')}</span>
                                    </div>
                                    {editingContact ? (
                                        <input
                                            value={contactInfo.phone}
                                            onChange={(e) => setContactInfo({ ...contactInfo, phone: e.target.value })}
                                            placeholder="+213..."
                                            className="w-full h-10 px-3 rounded-xl border border-slate-100 text-sm focus:outline-none focus:ring-4 focus:ring-blue-500/5 transition-all bg-slate-50/30"
                                        />
                                    ) : (
                                        <p className="text-sm font-semibold text-sky-950 pl-0.5 tracking-tight">
                                            {contactInfo.phone || profile.phone || <span className="text-slate-300 italic font-medium">{t('not_set')}</span>}
                                        </p>
                                    )}
                                </div>

                                <div className="space-y-1">
                                    <div className="flex items-center gap-2 text-slate-400/80">
                                        <MapPin className="w-3.5 h-3.5" />
                                        <span className="text-[10px] font-bold uppercase tracking-widest">{t('wilaya_label')}</span>
                                    </div>
                                    {editingContact ? (
                                        <input
                                            value={contactInfo.wilaya}
                                            onChange={(e) => setContactInfo({ ...contactInfo, wilaya: e.target.value })}
                                            placeholder="e.g. Algiers"
                                            className="w-full h-10 px-3 rounded-xl border border-slate-100 text-sm focus:outline-none focus:ring-4 focus:ring-blue-500/5 transition-all bg-slate-50/30"
                                        />
                                    ) : (
                                        <p className="text-sm font-semibold text-sky-950 pl-0.5 tracking-tight">
                                            {contactInfo.wilaya || profile.wilaya || <span className="text-slate-300 italic font-medium">{t('not_set')}</span>}
                                        </p>
                                    )}
                                </div>

                                <div className="space-y-1">
                                    <div className="flex items-center gap-2 text-slate-400/80">
                                        <Settings className="w-3.5 h-3.5" />
                                        <span className="text-[10px] font-bold uppercase tracking-widest">{t('address_label')}</span>
                                    </div>
                                    {editingContact ? (
                                        <input
                                            value={contactInfo.address}
                                            onChange={(e) => setContactInfo({ ...contactInfo, address: e.target.value })}
                                            placeholder="Street name, City"
                                            className="w-full h-10 px-3 rounded-xl border border-slate-100 text-sm focus:outline-none focus:ring-4 focus:ring-blue-500/5 transition-all bg-slate-50/30"
                                        />
                                    ) : (
                                        <p className="text-sm font-semibold text-sky-950 pl-0.5 tracking-tight">
                                            {contactInfo.address || <span className="text-slate-300 italic font-medium">{t('not_set')}</span>}
                                        </p>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Medical Info */}
                        <div className="bg-white border border-slate-200/60 shadow-sm rounded-[24px] overflow-hidden">
                            <div className="bg-slate-50/50 px-6 py-4 border-b border-slate-100/30 flex items-center justify-between">
                                <h3 className="text-[13px] font-medium text-slate-400/80">{t('medical_info')}</h3>
                                <button onClick={() => editingMedInfo ? saveMedicalInfo() : setEditingMedInfo(true)} className="text-[11px] font-bold text-blue-600 hover:underline">
                                    {editingMedInfo ? t('save') : t('edit')}
                                </button>
                            </div>
                            <div className="px-6 py-6 space-y-6">
                                {[
                                    { key: 'blood_type', label: t('blood_type_label'), icon: Heart, placeholder: 'e.g. O+' },
                                    { key: 'allergies', label: t('allergies_label'), icon: AlertTriangle, placeholder: 'e.g. Penicillin' },
                                    { key: 'conditions', label: t('conditions_label'), icon: Activity, placeholder: 'e.g. Hypertension' },
                                    { key: 'emergency_contact', label: t('emergency_label'), icon: Phone, placeholder: 'e.g. +213...' },
                                ].map(({ key, label, icon: Icon, placeholder }) => (
                                    <div key={key} className="space-y-1">
                                        <div className="flex items-center gap-2 text-slate-400/80">
                                            <Icon className="w-3.5 h-3.5" />
                                            <span className="text-[10px] font-bold uppercase tracking-widest">{label}</span>
                                        </div>
                                        {editingMedInfo ? (
                                            <input
                                                value={medicalInfo[key]}
                                                onChange={(e) => setMedicalInfo({ ...medicalInfo, [key]: e.target.value })}
                                                placeholder={placeholder}
                                                className="w-full h-10 px-3 rounded-xl border border-slate-100 text-sm focus:outline-none focus:ring-4 focus:ring-blue-500/5 transition-all bg-slate-50/30"
                                            />
                                        ) : (
                                            <p className="text-sm font-semibold text-sky-950 pl-0.5 tracking-tight">
                                                {medicalInfo[key] || <span className="text-slate-300 italic font-medium">{t('not_set')}</span>}
                                            </p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Medora card */}
                        <div className="bg-[#061225] rounded-[24px] p-7 text-white shadow-xl shadow-blue-900/10 relative overflow-hidden group">
                            <div className="absolute -right-6 -bottom-6 opacity-[0.1] group-hover:scale-110 group-hover:-rotate-12 transition-all duration-500"><Shield className="w-32 h-32 text-white" /></div>
                            <div className="relative z-10">
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="p-2 bg-blue-500/20 rounded-xl"><CheckCircle2 className="w-5 h-5 text-blue-400" /></div>
                                    <h4 className="font-bold text-base text-white tracking-tight">{t('protected')}</h4>
                                </div>
                                <Separator className="bg-white/10 mb-4" />
                                <p className="text-blue-100/70 text-xs leading-relaxed font-light">{t('protected_desc')}</p>
                            </div>
                        </div>
                    </div>

                    {/* Main: Medications */}
                    <div className="lg:col-span-2 space-y-6">
                        <div className="bg-white border border-slate-200/60 rounded-[24px] shadow-sm overflow-hidden">
                            <div className="border-b border-slate-100/50 px-8 py-6 flex items-center justify-between bg-white">
                                <div className="flex items-center gap-4">
                                    <div className="w-12 h-12 rounded-2xl bg-blue-50/50 flex items-center justify-center border border-blue-100/30"><Pill className="w-6 h-6 text-blue-600" /></div>
                                    <div>
                                        <h2 className="text-xl font-bold text-sky-950 tracking-tighter">{t('medications')}</h2>
                                        <p className="text-xs text-slate-400 font-light">{t('my_meds_desc')}</p>
                                    </div>
                                </div>
                                <span className="text-[10px] font-bold text-blue-600 bg-blue-50/50 px-3 py-1 rounded-full border border-blue-100/30 uppercase tracking-widest">{savedMeds.length} {t('saved')}</span>
                            </div>

                            <div className="p-8">
                                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-3">{t('add_med')}</p>

                                {/* Search */}
                                <div className="relative mb-4">
                                    <div className="relative">
                                        <input type="text" placeholder="Search by drug name..." value={medSearchTerm} onChange={(e) => setMedSearchTerm(e.target.value)}
                                            className="w-full h-10 pl-9 pr-4 rounded-lg border border-slate-200 bg-white text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all" />
                                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                    </div>
                                    {medSuggestions.length > 0 && (
                                        <div className="absolute z-50 w-full mt-1 rounded-lg border border-slate-200 bg-white shadow-lg overflow-hidden max-h-48 overflow-y-auto">
                                            {medSuggestions.map((drug, i) => (
                                                <button key={i} onClick={() => addMedToProfile(drug)} disabled={addingMed}
                                                    className="w-full text-left px-4 py-3 hover:bg-slate-50 flex items-center justify-between border-b border-slate-50 last:border-none transition-colors">
                                                    <div>
                                                        <p className="text-sm font-medium text-slate-900">{drug.brand_name || drug.generic_name}</p>
                                                        <p className="text-[10px] text-slate-500">{drug.form} · {drug.dosage}</p>
                                                    </div>
                                                    <Plus className="w-4 h-4 text-emerald-500" />
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                {/* Upload */}
                                <div onDragOver={(e) => { e.preventDefault(); setDragOver(true); }} onDragLeave={() => setDragOver(false)} onDrop={handleFileDrop} onClick={() => fileInputRef.current?.click()}
                                    className={`relative rounded-xl border-2 border-dashed transition-all cursor-pointer mb-6 ${dragOver ? 'border-primary bg-primary/5' : uploadedFile ? 'border-emerald-300 bg-emerald-50/30' : 'border-slate-200 bg-slate-50/30 hover:border-slate-300'} ${uploadedFile ? 'px-4 py-3' : 'px-4 py-5'}`}>
                                    <input ref={fileInputRef} type="file" accept="image/*,.pdf" onChange={handleFileDrop} className="hidden" />
                                    {uploadedFile ? (
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center"><FileImage className="w-4 h-4 text-emerald-600" /></div>
                                                <div>
                                                    <p className="text-sm font-medium text-slate-900 truncate max-w-[200px]">{uploadedFile.name}</p>
                                                    <p className="text-[10px] text-slate-500">{(uploadedFile.size / 1024).toFixed(0)} KB</p>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <button onClick={(e) => { e.stopPropagation(); handleUploadScan(); }} disabled={uploading}
                                                    className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md bg-primary text-white text-xs font-medium hover:bg-primary/90 disabled:opacity-50">
                                                    {uploading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />} Scan
                                                </button>
                                                <button onClick={(e) => { e.stopPropagation(); setUploadedFile(null); }} className="p-1 text-slate-400 hover:text-red-500"><X className="w-4 h-4" /></button>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="flex items-center gap-4">
                                            <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center shrink-0"><Upload className="w-5 h-5 text-slate-400" /></div>
                                            <div>
                                                <p className="text-sm font-medium text-slate-600">Upload Prescription</p>
                                                <p className="text-[10px] text-slate-400">Drop an image or PDF to auto-extract medications</p>
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* Saved meds */}
                                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-3">Saved Medications</p>
                                {loadingMeds ? (
                                    <div className="py-10 text-center"><Loader2 className="w-6 h-6 text-primary animate-spin mx-auto mb-2" /><p className="text-xs text-slate-400">Loading...</p></div>
                                ) : savedMeds.length === 0 ? (
                                    <div className="py-10 text-center border border-dashed border-slate-100 rounded-xl bg-slate-50/30">
                                        <Pill className="w-8 h-8 text-slate-200 mx-auto mb-3" />
                                        <p className="text-sm text-slate-400 font-medium">No medications saved yet</p>
                                        <p className="text-xs text-slate-400 mt-1">Search or upload a prescription to add</p>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        {savedMeds.map((med) => (
                                            <div key={med.id} className="flex items-center justify-between px-4 py-3 rounded-xl border border-slate-100 hover:border-slate-200 transition-colors group">
                                                <div className="flex items-center gap-3 min-w-0">
                                                    <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center shrink-0 border border-emerald-100"><Pill className="w-4 h-4 text-emerald-500" /></div>
                                                    <div className="min-w-0">
                                                        <p className="text-sm font-semibold text-slate-900 truncate">{med.drug?.brand_name || med.drug?.generic_name}</p>
                                                        <p className="text-[10px] text-slate-500 truncate">{med.drug?.form} · {med.drug?.dosage}</p>
                                                    </div>
                                                </div>
                                                <button onClick={() => removeMed(med.id)} className="p-1.5 text-slate-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all shrink-0"><Trash2 className="w-4 h-4" /></button>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

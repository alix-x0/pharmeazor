import React, { useState, useEffect, useCallback } from 'react';
import { Search, Plus, Trash2, AlertTriangle, CheckCircle, AlertCircle, Info, Sparkles, ShieldCheck, Activity, Languages, Stethoscope } from 'lucide-react';
import { useLanguage } from "../contexts/LanguageContext";
import api from '@/api/api';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

// Mock drug database for demo
const MOCK_DRUGS = [
    { id: 1, name: "Aspirine", brand: "Aspegic", type: "Antalgique" },
    { id: 2, name: "Ibuprofène", brand: "Advil", type: "AINS" },
    { id: 3, name: "Paracétamol", brand: "Doliprane", type: "Antalgique" },
    { id: 4, name: "Amoxicilline", brand: "Clamoxyl", type: "Antibiotique" },
    { id: 5, name: "Metformine", brand: "Glucophage", type: "Antidiabétique" },
    { id: 6, name: "Sintrom", brand: "Acénocoumarol", type: "Anticoagulant" },
    { id: 7, name: "Diclofénac", brand: "Voltarene", type: "AINS" },
    { id: 8, name: "Spasfon", brand: "Phloroglucinol", type: "Antispasmodique" },
];

const Interactions = () => {
    const { t } = useLanguage();
    const [searchTerm, setSearchTerm] = useState("");
    const [suggestions, setSuggestions] = useState([]);
    const [selectedDrugs, setSelectedDrugs] = useState([]);
    const [results, setResults] = useState(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [searching, setSearching] = useState(false);
    const [selectedLanguage, setSelectedLanguage] = useState("darija");

    // Fetch drug suggestions from backend
    useEffect(() => {
        const fetchSuggestions = async () => {
            if (searchTerm.length < 2) {
                setSuggestions([]);
                return;
            }

            setSearching(true);
            try {
                const response = await api.get(`/drugs/?search=${searchTerm}`);
                // Ensure we don't suggest drugs already selected
                const filtered = response.data.results.filter(
                    drug => !selectedDrugs.find(sd => sd.registration_number === drug.registration_number)
                );
                setSuggestions(filtered);
            } catch (error) {
                console.error("Error searching drugs:", error);
            } finally {
                setSearching(false);
            }
        };

        const timeoutId = setTimeout(fetchSuggestions, 300);
        return () => clearTimeout(timeoutId);
    }, [searchTerm, selectedDrugs]);

    const addDrug = (drug) => {
        setSelectedDrugs([...selectedDrugs, drug]);
        setSearchTerm("");
        setSuggestions([]);
        setResults(null);
    };

    const removeDrug = (regNum) => {
        setSelectedDrugs(selectedDrugs.filter(d => d.registration_number !== regNum));
        setResults(null);
    };

    const analyzeInteractions = async () => {
        if (selectedDrugs.length < 2) return;

        setAnalyzing(true);
        try {
            // We only need the names for the analysis engine
            const drugNames = selectedDrugs.map(d => d.brand_name || d.generic_name);
            const response = await api.post("/interactions/analyze/", { 
                drugs: drugNames,
                user_role: "patient"
            });
            setResults(response.data);
        } catch (error) {
            console.error("Error analyzing interactions:", error);
            alert(t('analysis_failed') || "Analysis failed.");
        } finally {
            setAnalyzing(false);
        }
    };

    return (
        <div className="max-w-7xl mx-auto py-12 px-6 animate-in fade-in duration-700">
            {/* Minimalist Apple-Style Header in a Box */}
            <div className="mb-14 p-10 md:p-12 bg-blue-50/50 dark:bg-blue-900/10 border border-blue-100/50 dark:border-blue-900/20 rounded-[2rem] text-center max-w-4xl mx-auto shadow-sm">
                <h1 className="text-3xl sm:text-4xl font-semibold text-slate-900 tracking-tight mb-4">
                    {t('inter_title')}
                </h1>

                <p className="text-base text-slate-500 leading-relaxed mb-8 max-w-2xl mx-auto">
                    {t('inter_desc')}
                </p>

                <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-4 text-sm text-slate-500 font-medium">
                    <div className="flex items-center gap-2">
                        <Activity className="w-4 h-4 text-blue-400" />
                        <span>{t('real_time_sync')}</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4 text-blue-400" />
                        <span>{t('ddinter_verified')}</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <Languages className="w-4 h-4 text-blue-400" />
                        <span>{t('multi_lingual')}</span>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
                {/* Left Column: Input */}
                <div className="lg:col-span-1 space-y-4">
                    <div className="bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-sm overflow-hidden">
                        {/* Header */}
                        <div className="px-5 py-4 border-b border-zinc-100 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-lg border border-blue-100 dark:border-blue-800/30">
                                    <Search className="w-4 h-4" />
                                </div>
                                <div>
                                    <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{t('add_meds')}</h2>
                                    <p className="text-xs text-zinc-500 dark:text-zinc-400">{t('search_generic')}</p>
                                </div>
                            </div>
                        </div>

                        {/* Content */}
                        <div className="p-5">
                            {/* Search Input */}
                            <div className="relative group">
                                <input
                                    type="text"
                                    placeholder={t('search_placeholder')}
                                    value={searchTerm}
                                    onChange={(e) => setSearchTerm(e.target.value)}
                                    className="w-full pl-9 pr-3 h-10 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-md text-sm text-zinc-900 dark:text-zinc-50 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all shadow-sm"
                                />
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400 group-focus-within:text-blue-500 transition-colors" />

                                {suggestions.length > 0 && (
                                    <div className="absolute z-50 w-full mt-2 bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-lg shadow-xl overflow-hidden ring-1 ring-black/5">
                                        <div className="px-3 py-2 bg-zinc-50/80 dark:bg-zinc-900/80 border-b border-zinc-100 dark:border-zinc-800 flex justify-between items-center">
                                            <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-widest">{t('suggestions')}</p>
                                            {searching && <div className="w-3 h-3 border border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>}
                                        </div>
                                        <div className="max-h-52 overflow-y-auto py-1">
                                            {suggestions.map((drug, index) => (
                                                <button
                                                    key={drug.registration_number || index}
                                                    onClick={() => addDrug(drug)}
                                                    className="w-full text-left px-3 py-2.5 hover:bg-zinc-50 dark:hover:bg-zinc-900 flex items-center justify-between group transition-colors"
                                                >
                                                    <div className="min-w-0 pr-3">
                                                        <p className="font-medium text-sm text-zinc-900 dark:text-zinc-50 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors truncate">{drug.brand_name || drug.generic_name}</p>
                                                        <p className="text-[10px] text-zinc-500 truncate mt-0.5">{drug.form} • {drug.dosage}</p>
                                                    </div>
                                                    <div className="w-6 h-6 rounded-md bg-zinc-100 dark:bg-zinc-800 group-hover:bg-blue-600 group-hover:text-white flex items-center justify-center transition-all shrink-0">
                                                        <Plus className="w-3.5 h-3.5" />
                                                    </div>
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Selected List Section */}
                            <div className="mt-6">
                                <h3 className="text-xs font-semibold text-zinc-900 dark:text-zinc-50 mb-3">
                                    {t('selected_drugs')} <span className="text-zinc-400 font-normal">({selectedDrugs.length})</span>
                                </h3>

                                {selectedDrugs.length === 0 ? (
                                    <div className="text-center py-8 px-4 border border-dashed border-zinc-200 dark:border-zinc-800 rounded-lg bg-zinc-50/50 dark:bg-zinc-900/20">
                                        <p className="text-xs text-zinc-400">{t('no_drugs')}</p>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        {selectedDrugs.map((drug, index) => (
                                            <div key={drug.registration_number || index} className="flex items-center justify-between px-3 py-2.5 bg-white dark:bg-zinc-950 rounded-md border border-zinc-200 dark:border-zinc-800 shadow-sm group hover:border-blue-200 dark:hover:border-blue-900 transition-all">
                                                <div className="min-w-0 pr-2">
                                                    <p className="font-medium text-sm text-zinc-900 dark:text-zinc-50 truncate">{drug.brand_name || drug.generic_name}</p>
                                                    <p className="text-[10px] text-zinc-500 truncate mt-0.5">{drug.form}</p>
                                                </div>
                                                <button
                                                    onClick={() => removeDrug(drug.registration_number)}
                                                    className="p-1.5 text-zinc-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-all shrink-0"
                                                >
                                                    <Trash2 className="w-3.5 h-3.5" />
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>

                            {/* Action Button */}
                            <div className="mt-6">
                                <button
                                    disabled={selectedDrugs.length < 2 || analyzing}
                                    onClick={analyzeInteractions}
                                    className="w-full h-10 bg-blue-600 text-white font-medium text-sm rounded-md shadow-sm hover:bg-blue-700 active:scale-[0.98] transition-all disabled:bg-zinc-100 dark:disabled:bg-zinc-800 disabled:text-zinc-400 disabled:shadow-none disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                >
                                    {analyzing ? (
                                        <>
                                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                            <span>{t('analyzing')}</span>
                                        </>
                                    ) : (
                                        <>
                                            <Activity className="w-4 h-4" />
                                            <span>{t('analyze_btn')}</span>
                                        </>
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>

                    <div className="px-4 py-3 bg-blue-50/50 dark:bg-blue-900/10 rounded-lg border border-blue-100/60 dark:border-blue-900/30">
                        <div className="flex gap-2">
                            <Info className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
                            <p className="text-xs text-blue-800 dark:text-blue-300 leading-relaxed">
                                <span className="font-semibold">{t('clinical_note')}</span> {t('disclaimer')}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Right Column: Results */}
                <div className="lg:col-span-2 min-h-[500px]">
                    {!results && !analyzing && (
                        <div className="h-full bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-8 flex flex-col justify-center shadow-sm">
                            <div className="max-w-2xl mx-auto space-y-8 w-full">
                                <div className="border-b border-zinc-100 dark:border-zinc-800 pb-6 mb-6 flex items-start gap-4">
                                    <div className="p-4 bg-sky-50 dark:bg-sky-900/20 text-sky-600 dark:text-sky-400 rounded-[16px] shrink-0 border border-sky-100 dark:border-sky-900/30">
                                        <ShieldCheck className="w-7 h-7" />
                                    </div>
                                    <div>
                                        <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{t('analysis_engine')}</h3>
                                        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1.5 leading-relaxed">
                                            {t('engine_desc')}
                                        </p>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    <div className="p-5 bg-red-50/50 dark:bg-red-900/10 border border-red-100 dark:border-red-900/30 rounded-xl">
                                        <h4 className="text-sm font-bold text-red-700 dark:text-red-400 flex items-center gap-2 mb-2">
                                            <span className="w-2 h-2 rounded-full bg-red-500"></span>
                                            {t('major_inter')}
                                        </h4>
                                        <p className="text-xs text-red-600/80 dark:text-red-300/80 leading-relaxed">
                                            Highly clinically significant. Risk of dangerous adverse effects or therapeutic failure. Avoid combination if possible or monitor strictly.
                                        </p>
                                    </div>

                                    <div className="p-5 bg-yellow-50/50 dark:bg-yellow-900/10 border border-yellow-100 dark:border-yellow-900/30 rounded-xl">
                                        <h4 className="text-sm font-bold text-yellow-700 dark:text-yellow-400 flex items-center gap-2 mb-2">
                                            <span className="w-2 h-2 rounded-full bg-yellow-500"></span>
                                            {t('moderate_inter')}
                                        </h4>
                                        <p className="text-xs text-yellow-600/80 dark:text-yellow-300/80 leading-relaxed">
                                            Moderately clinically significant. Usually requires dosage adjustments, altered timing of administration, or close clinical monitoring.
                                        </p>
                                    </div>

                                    <div className="p-5 bg-emerald-50/50 dark:bg-emerald-900/10 border border-emerald-100 dark:border-emerald-900/30 rounded-xl sm:col-span-2">
                                        <h4 className="text-sm font-bold text-emerald-700 dark:text-emerald-400 flex items-center gap-2 mb-2">
                                            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                                            {t('minor_inter')}
                                        </h4>
                                        <p className="text-xs text-emerald-600/80 dark:text-emerald-300/80 leading-relaxed">
                                            Minimal clinical significance. May cause minor effects but typically does not require a change in therapy. Standard monitoring is advised.
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {analyzing && (
                        <div className="h-full flex flex-col items-center justify-center p-20 space-y-6">
                            <div className="relative w-24 h-24">
                                <div className="absolute inset-0 border-4 border-primary/10 rounded-full"></div>
                                <div className="absolute inset-0 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <Activity className="w-8 h-8 text-primary animate-pulse" />
                                </div>
                            </div>
                            <div className="text-center">
                                <h3 className="text-xl font-bold text-slate-900 mb-2">{t('scanning_db')}</h3>
                                <p className="text-sm text-slate-500 font-medium">{t('pairs_analyzed')} ({selectedDrugs.length})</p>
                            </div>
                        </div>
                    )}

                    {results && (
                        <div className="space-y-6 animate-in slide-in-from-bottom-6 duration-700">
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 px-2">
                                <div className="flex items-center gap-3">
                                    <h3 className="text-2xl font-bold text-slate-900">{t('analysis_results')}</h3>
                                    <Badge variant="secondary" className="bg-white border border-slate-100 text-slate-600 px-4 py-1 rounded-full font-bold shadow-sm">
                                        {results.explained_pairs?.length || 0} {t('pairs_analyzed')}
                                    </Badge>
                                </div>

                                <div className="flex bg-slate-100 p-1 rounded-xl w-fit self-end sm:self-auto">
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setSelectedLanguage("darija")}
                                        className={`h-8 px-4 text-[10px] font-bold rounded-lg transition-all ${selectedLanguage === "darija" ? "bg-white shadow-sm text-primary" : "text-slate-500 hover:text-slate-700"}`}
                                    >
                                        DARIJA
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setSelectedLanguage("french")}
                                        className={`h-8 px-4 text-[10px] font-bold rounded-lg transition-all ${selectedLanguage === "french" ? "bg-white shadow-sm text-primary" : "text-slate-500 hover:text-slate-700"}`}
                                    >
                                        FRENCH
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setSelectedLanguage("english")}
                                        className={`h-8 px-4 text-[10px] font-bold rounded-lg transition-all ${selectedLanguage === "english" ? "bg-white shadow-sm text-primary" : "text-slate-500 hover:text-slate-700"}`}
                                    >
                                        ENGLISH
                                    </Button>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 gap-5">
                                {results.explained_pairs?.map((res, idx) => (
                                    <div key={idx} className="bg-white dark:bg-zinc-950 overflow-hidden shadow-sm border border-zinc-200 dark:border-zinc-800 rounded-2xl transition-all" style={{ borderColor: res.color ? `${res.color}44` : undefined }}>
                                        {/* Top Color Bar */}
                                        <div className="h-2 w-full" style={{ backgroundColor: res.color || '#94a3b8' }}></div>

                                        <div>
                                            <div className="p-6">
                                                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                                                    <div className="flex items-center gap-4">
                                                        <div className="flex items-center bg-zinc-50 dark:bg-zinc-900 p-1.5 rounded-xl border border-zinc-200 dark:border-zinc-800">
                                                            <div className="px-4 py-1.5 bg-white dark:bg-zinc-950 rounded-lg font-semibold text-sm shadow-sm">{res.drug_a}</div>
                                                            <div className="px-3">
                                                                <Activity className="w-4 h-4 text-zinc-400" />
                                                            </div>
                                                            <div className="px-4 py-1.5 bg-white dark:bg-zinc-950 rounded-lg font-semibold text-sm shadow-sm">{res.drug_b}</div>
                                                        </div>
                                                    </div>

                                                    <div className="text-white px-4 py-1.5 rounded-lg font-bold text-xs shadow-sm" style={{ backgroundColor: res.color || '#94a3b8' }}>
                                                        {res.level}
                                                    </div>
                                                </div>

                                                <div className="grid grid-cols-1 gap-5">
                                                    <div className="p-6 bg-zinc-50/80 dark:bg-zinc-900/50 rounded-2xl border border-zinc-100 dark:border-zinc-800 shadow-inner">
                                                        <div className="flex items-center justify-between mb-4">
                                                            <div className="flex items-center gap-2">
                                                                <div className="p-1.5 bg-white dark:bg-zinc-950 rounded-lg shadow-sm">
                                                                    <Languages className="w-4 h-4 text-blue-500" />
                                                                </div>
                                                                <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">
                                                                    {selectedLanguage === "darija" ? "Explication en Darija" :
                                                                        selectedLanguage === "french" ? "Explication en Français" :
                                                                            "English Explanation"}
                                                                </p>
                                                            </div>
                                                            <div className="p-1.5 bg-blue-50 dark:bg-blue-900/20 rounded-full">
                                                                <Sparkles className="w-3 h-3 text-blue-500 animate-pulse" />
                                                            </div>
                                                        </div>

                                                        <p
                                                            className={`text-sm font-semibold text-zinc-800 dark:text-zinc-200 leading-relaxed ${selectedLanguage === "darija" ? "text-right" : "text-left"}`}
                                                            dir={selectedLanguage === "darija" ? "rtl" : "ltr"}
                                                        >
                                                            "{selectedLanguage === "darija" ? res.darija_explanation :
                                                                selectedLanguage === "french" ? res.french_explanation :
                                                                    res.medical_explanation}"
                                                        </p>

                                                        {selectedLanguage === "darija" && res.darija_risk_label && (
                                                            <div className="mt-4 flex justify-end">
                                                                <div className="text-[10px] border border-blue-200 dark:border-blue-800 text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 px-3 py-1 rounded-full font-bold" dir="rtl">{res.darija_risk_label}</div>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>

                                            {/* Footer */}
                                            <div className="px-6 py-3.5 bg-zinc-50/50 dark:bg-zinc-900/30 border-t border-zinc-100 dark:border-zinc-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                                                <div className="flex items-center gap-3">
                                                    <div className="p-1.5 rounded-lg" style={{ backgroundColor: (res.color || '#94a3b8') + '22' }}>
                                                        {res.level === 'DANGER' ? <AlertTriangle className="w-4 h-4" style={{ color: res.color }} /> :
                                                            res.level === 'CAUTION' ? <AlertCircle className="w-4 h-4" style={{ color: res.color }} /> :
                                                                <CheckCircle className="w-4 h-4" style={{ color: res.color }} />}
                                                    </div>
                                                    <span className="text-[11px] font-extrabold tracking-tight uppercase" style={{ color: res.color || '#94a3b8' }}>
                                                        {res.level === 'DANGER' ? 'CRITICAL RISK DETECTED' :
                                                            res.level === 'CAUTION' ? 'MODERATE PRECAUTION' :
                                                                'PROCEED WITH CARE'}
                                                    </span>
                                                </div>
                                                <button className="flex items-center gap-2 h-9 px-4 text-[12px] font-semibold text-white bg-red-600 hover:bg-red-700 rounded-[10px] transition-all active:scale-[0.98] shadow-sm shadow-red-600/20">
                                                    <AlertTriangle className="w-3.5 h-3.5" />
                                                    {t('report_incident')}
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default Interactions;

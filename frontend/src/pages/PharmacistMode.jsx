import React, { useState, useEffect } from 'react';
import {
    Search,
    Trash2,
    Activity,
    Database,
    ExternalLink,
    FileText,
    ShieldCheck,
    Clock,
    Stethoscope,
    Info,
    ArrowLeft
} from 'lucide-react';
import api from '@/api/api';
import { useNavigate } from 'react-router-dom';

const PharmacistMode = () => {
    const navigate = useNavigate();
    const [drugA, setDrugA] = useState(null);
    const [drugB, setDrugB] = useState(null);
    const [activeSlot, setActiveSlot] = useState("A"); // which slot the search fills
    const [searchTerm, setSearchTerm] = useState("");
    const [suggestions, setSuggestions] = useState([]);
    const [result, setResult] = useState(null);
    const [analyzing, setAnalyzing] = useState(false);

    useEffect(() => {
        const fetchSuggestions = async () => {
            if (searchTerm.length < 2) {
                setSuggestions([]);
                return;
            }
            try {
                const response = await api.get(`/drugs/?search=${searchTerm}`);
                const existing = [drugA, drugB].filter(Boolean).map(d => d.registration_number);
                setSuggestions(response.data.results.filter(d => !existing.includes(d.registration_number)));
            } catch (e) { console.error(e); }
        };
        const timer = setTimeout(fetchSuggestions, 300);
        return () => clearTimeout(timer);
    }, [searchTerm, drugA, drugB]);

    const selectDrug = (drug) => {
        if (activeSlot === "A") {
            setDrugA(drug);
            if (!drugB) setActiveSlot("B");
        } else {
            setDrugB(drug);
        }
        setSearchTerm("");
        setSuggestions([]);
        setResult(null);
    };

    const clearSlot = (slot) => {
        if (slot === "A") setDrugA(null);
        else setDrugB(null);
        setResult(null);
    };

    const analyzePair = async () => {
        if (!drugA || !drugB) return;
        setAnalyzing(true);
        try {
            const drugNames = [drugA, drugB].map(d => d.brand_name || d.generic_name);
            const response = await api.post("/interactions/analyze/", { 
                drugs: drugNames,
                user_role: "pharmacist"
            });
            const pairs = response.data.explained_pairs || [];
            setResult(pairs[0] || null);
        } catch (e) {
            console.error(e);
        }
        finally { setAnalyzing(false); }
    };

    const drugLabel = (drug) => drug.brand_name || drug.generic_name;

    return (
        <div className="w-full pb-8 pt-2">
            {/* Header */}
            <div className="bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 mb-8 shadow-sm flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6">
                <div className="flex gap-4 items-start sm:items-center">
                    <div className="hidden sm:flex p-3 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-xl border border-blue-100 dark:border-blue-800/30">
                        <Stethoscope className="w-6 h-6" />
                    </div>
                    <div className="space-y-1.5">
                        <h1 className="text-xl md:text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50 flex items-center gap-2">
                            <span className="sm:hidden text-blue-600 dark:text-blue-400">
                                <Stethoscope className="w-5 h-5" />
                            </span>
                            Pharmacist Support Mode
                        </h1>
                        <p className="text-zinc-500 dark:text-zinc-400 text-sm max-w-2xl leading-relaxed">
                            Single-pair clinical analysis for precise patient counseling. Evaluate interaction risks, clinical consequences, and actionable recommendations.
                        </p>
                    </div>
                </div>
                <button
                    onClick={() => navigate('/dashboard')}
                    className="inline-flex items-center gap-2 h-9 px-4 rounded-md text-sm font-medium border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-zinc-700 dark:text-zinc-300 shadow-sm hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors shrink-0"
                >
                    <ArrowLeft className="w-4 h-4 text-zinc-500" />
                    Dashboard
                </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
                {/* Left: Drug Pair Input */}
                <div className="lg:col-span-1 space-y-4">
                    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-sm overflow-hidden">
                        <div className="px-4 py-3 border-b border-zinc-100 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50">
                            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50 flex items-center gap-2">
                                <Stethoscope className="w-3.5 h-3.5 text-primary" />
                                Drug Pair Selection
                            </h3>
                        </div>
                        <div className="p-4 space-y-4">
                            {/* Drug A */}
                            <div>
                                <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-2">Drug A</p>
                                {drugA ? (
                                    <div className="flex items-center justify-between px-3 py-2.5 rounded-md bg-zinc-50 dark:bg-zinc-900 border border-zinc-100 dark:border-zinc-800">
                                        <div className="min-w-0">
                                            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50 truncate">{drugLabel(drugA)}</p>
                                            <p className="text-[10px] text-zinc-400">{drugA.form} · {drugA.dosage}</p>
                                        </div>
                                        <button onClick={() => clearSlot("A")} className="ml-2 p-1 text-zinc-400 hover:text-red-500 transition-colors">
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                    </div>
                                ) : (
                                    <button
                                        onClick={() => setActiveSlot("A")}
                                        className={`w-full text-left px-3 py-3 rounded-md border border-dashed transition-colors ${activeSlot === "A" ? "border-primary bg-primary/5 text-primary" : "border-zinc-200 dark:border-zinc-800 text-zinc-400"}`}
                                    >
                                        <p className="text-xs font-medium">{activeSlot === "A" ? "Searching for Drug A..." : "Click to select Drug A"}</p>
                                    </button>
                                )}
                            </div>

                            {/* Drug B */}
                            <div>
                                <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-2">Drug B</p>
                                {drugB ? (
                                    <div className="flex items-center justify-between px-3 py-2.5 rounded-md bg-zinc-50 dark:bg-zinc-900 border border-zinc-100 dark:border-zinc-800">
                                        <div className="min-w-0">
                                            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50 truncate">{drugLabel(drugB)}</p>
                                            <p className="text-[10px] text-zinc-400">{drugB.form} · {drugB.dosage}</p>
                                        </div>
                                        <button onClick={() => clearSlot("B")} className="ml-2 p-1 text-zinc-400 hover:text-red-500 transition-colors">
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                    </div>
                                ) : (
                                    <button
                                        onClick={() => setActiveSlot("B")}
                                        className={`w-full text-left px-3 py-3 rounded-md border border-dashed transition-colors ${activeSlot === "B" ? "border-primary bg-primary/5 text-primary" : "border-zinc-200 dark:border-zinc-800 text-zinc-400"}`}
                                    >
                                        <p className="text-xs font-medium">{activeSlot === "B" ? "Searching for Drug B..." : "Click to select Drug B"}</p>
                                    </button>
                                )}
                            </div>

                            {/* Search input */}
                            {(!drugA || !drugB) && (
                                <div className="relative pt-2 border-t border-zinc-100 dark:border-zinc-800 mt-2">
                                    <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                                        Search for Drug {activeSlot}
                                    </p>
                                    <div className="relative">
                                        <input
                                            type="text"
                                            placeholder="Type a drug name..."
                                            value={searchTerm}
                                            onChange={(e) => setSearchTerm(e.target.value)}
                                            className="flex h-9 w-full rounded-md border border-zinc-200 dark:border-zinc-800 bg-transparent pl-8 pr-3 py-1 text-sm shadow-sm transition-colors placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary dark:text-zinc-50"
                                        />
                                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-400" />
                                    </div>

                                    {suggestions.length > 0 && (
                                        <div className="absolute z-50 w-full mt-1 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-md overflow-hidden max-h-52 overflow-y-auto">
                                            {suggestions.map((drug, i) => (
                                                <button
                                                    key={i}
                                                    onClick={() => selectDrug(drug)}
                                                    className="w-full text-left px-3 py-2.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 border-b border-zinc-50 dark:border-zinc-900 last:border-none transition-colors"
                                                >
                                                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50 truncate">{drug.brand_name || drug.generic_name}</p>
                                                    <p className="text-[10px] text-zinc-500 mt-0.5">{drug.form} · {drug.dosage}</p>
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Analyze button */}
                            <button
                                disabled={!drugA || !drugB || analyzing}
                                onClick={analyzePair}
                                className="inline-flex items-center justify-center gap-2 w-full h-9 mt-2 rounded-md bg-primary text-primary-foreground text-sm font-medium shadow-sm hover:bg-primary/90 transition-colors disabled:pointer-events-none disabled:opacity-50"
                            >
                                {analyzing ? (
                                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                ) : (
                                    <Activity className="w-4 h-4" />
                                )}
                                Analyze Pair
                            </button>
                        </div>
                    </div>

                    <div className="rounded-lg border border-blue-100 dark:border-blue-900/30 bg-blue-50/50 dark:bg-blue-950/20 p-4">
                        <div className="flex gap-2.5">
                            <Info className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
                            <p className="text-[11px] text-blue-700 dark:text-blue-400 leading-relaxed">
                                Select exactly two medications to check their clinical interaction profile.
                            </p>
                        </div>
                    </div>
                </div>

                {/* Right: Single Result */}
                <div className="lg:col-span-3 space-y-4">
                    {/* Header bar */}
                    <div className="rounded-lg bg-zinc-900 dark:bg-zinc-950 px-5 py-3 flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                            <Database className="w-4 h-4 text-primary" />
                            <span className="text-xs font-semibold text-white tracking-tight">Clinical Interaction Report</span>
                        </div>
                        <span className="text-[9px] font-medium text-zinc-500 border border-zinc-700 rounded px-2 py-0.5 uppercase tracking-wider">DDInter 2024</span>
                    </div>

                    {/* Empty state */}
                    {!result && !analyzing && (
                        <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-sm min-h-[450px] flex items-center justify-center">
                            <div className="flex flex-col items-center gap-3 text-center px-8">
                                <Stethoscope className="w-10 h-10 text-zinc-200 dark:text-zinc-800" />
                                <div>
                                    <p className="text-sm font-medium text-zinc-400">Awaiting Drug Pair</p>
                                    <p className="text-xs text-zinc-400 mt-1">Select Drug A and Drug B, then run analysis to generate a clinical report.</p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Loading */}
                    {analyzing && (
                        <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-sm min-h-[450px] flex items-center justify-center">
                            <div className="flex flex-col items-center gap-3">
                                <div className="w-8 h-8 border-4 border-zinc-200 dark:border-zinc-800 border-t-primary rounded-full animate-spin"></div>
                                <p className="text-sm text-zinc-400">Querying DDInter database...</p>
                            </div>
                        </div>
                    )}

                    {/* Single result card */}
                    {result && (
                        <>
                            <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-sm overflow-hidden">
                                {/* Color severity bar */}
                                <div className="h-1.5" style={{ backgroundColor: result.color || '#71717a' }}></div>

                                {/* Drug pair header */}
                                <div className="px-6 py-5 flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800">
                                    <div className="flex items-center gap-3">
                                        <span className="text-base font-bold text-zinc-900 dark:text-zinc-50">{result.drug_a}</span>
                                        <span className="text-zinc-300 dark:text-zinc-600 text-lg">×</span>
                                        <span className="text-base font-bold text-zinc-900 dark:text-zinc-50">{result.drug_b}</span>
                                    </div>
                                    <span
                                        className="inline-flex items-center rounded-md px-3 py-1 text-xs font-bold text-white uppercase tracking-wide"
                                        style={{ backgroundColor: result.color || '#71717a' }}
                                    >
                                        {result.level}
                                    </span>
                                </div>

                                {/* Mechanism */}
                                <div className="px-6 py-5">
                                    <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-3">Clinical Mechanism</p>
                                    <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed">
                                        {result.medical_explanation}
                                    </p>
                                </div>

                                {/* Metadata row */}
                                <div className="px-6 py-4 bg-zinc-50/50 dark:bg-zinc-900/30 border-t border-zinc-100 dark:border-zinc-800 flex flex-wrap items-center gap-x-8 gap-y-3">
                                    <div>
                                        <p className="text-[10px] font-semibold text-zinc-400 uppercase mb-1">Confidence</p>
                                        <div className="flex items-center gap-2">
                                            <div className="h-1.5 w-20 rounded-full bg-zinc-200 dark:bg-zinc-800 overflow-hidden">
                                                <div className="h-full rounded-full bg-emerald-500" style={{ width: `${(result.confidence || 0.85) * 100}%` }}></div>
                                            </div>
                                            <span className="text-sm font-bold text-zinc-700 dark:text-zinc-300">{((result.confidence || 0.85) * 100).toFixed(0)}%</span>
                                        </div>
                                    </div>
                                    <div>
                                        <p className="text-[10px] font-semibold text-zinc-400 uppercase mb-1">Source</p>
                                        <div className="flex items-center gap-1.5">
                                            <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                                            <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{result.source || "DDInter"}</span>
                                        </div>
                                    </div>
                                    <div>
                                        <p className="text-[10px] font-semibold text-zinc-400 uppercase mb-1">Classification</p>
                                        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{result.level}</span>
                                    </div>
                                </div>
                            </div>

                            {/* Actions */}
                            <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-sm px-5 py-4 flex items-center justify-between">
                                <p className="text-[11px] text-zinc-500 max-w-sm leading-relaxed">
                                    Cross-reference with institutional pharmacy protocols before dispensing.
                                </p>
                                <div className="flex gap-2">
                                    <button className="inline-flex items-center gap-2 h-9 px-4 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-sm font-medium text-zinc-700 dark:text-zinc-300 shadow-sm hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors">
                                        Archive
                                    </button>
                                    <button className="inline-flex items-center gap-2 h-9 px-4 rounded-md bg-emerald-600 text-white text-sm font-medium shadow-sm hover:bg-emerald-700 transition-colors">
                                        <FileText className="w-4 h-4" />
                                        Export PDF
                                    </button>
                                </div>
                            </div>
                        </>
                    )}

                    {/* Bottom cards */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
                        <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-900 text-white p-5 shadow-sm">
                            <div className="flex items-center gap-2 mb-2">
                                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                                <h4 className="text-sm font-semibold">Professional Guidelines</h4>
                            </div>
                            <p className="text-xs text-zinc-400 leading-relaxed mb-4">
                                All results are sourced from the DDInter pharmacological database and BioMistral clinical inference engine.
                            </p>
                            <button className="inline-flex items-center h-8 px-3 rounded-md bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-700 transition-colors">
                                View Protocols
                            </button>
                        </div>
                        <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-blue-600 text-white p-5 shadow-sm">
                            <div className="flex items-center gap-2 mb-2">
                                <Clock className="w-4 h-4 text-blue-200" />
                                <h4 className="text-sm font-semibold">Audit Trail</h4>
                            </div>
                            <p className="text-xs text-blue-100 leading-relaxed mb-4">
                                Record this clinical decision in the pharmacy's dispensing log for regulatory compliance.
                            </p>
                            <button className="inline-flex items-center h-8 px-3 rounded-md bg-white/10 border border-white/20 text-white text-xs font-medium hover:bg-white/20 transition-colors">
                                Commit Audit
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PharmacistMode;

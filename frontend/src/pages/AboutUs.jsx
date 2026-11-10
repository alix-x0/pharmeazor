import React from "react";
import {
    Users, Target, Award, Rocket,
    ArrowRight, Heart, Brain, Zap, Briefcase, GraduationCap, ShieldCheck, Activity, Languages, Stethoscope, Search, Sparkles
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { useLanguage } from "../contexts/LanguageContext";

const team = [
    {
        name: "Dr. Amine Mansouri",
        role: "Chief Medical Officer",
        initials: "AM",
        bio: "Pharmacologist with 15 years of experience in clinical drug safety and patient advocacy.",
        tag: "Medical Lead"
    },
    {
        name: "Sarah Benali",
        role: "Head of AI Engineering",
        initials: "SB",
        bio: "Expert in NLP and medical data processing, dedicated to making clinical data accessible in Darija.",
        tag: "Tech Lead"
    },
    {
        name: "Reda Belkacem",
        role: "Pharmacist Relations",
        initials: "RB",
        bio: "Ensuring Medora integrates seamlessly into the daily workflow of Algerian community pharmacies.",
        tag: "Operations"
    }
];

const stats = [
    { label: "Active Users", value: "250+", icon: Briefcase },
    { label: "Verified Records", value: "236k+", icon: ShieldCheck },
    { label: "Partner Pharmacies", value: "100+", icon: Rocket },
    { label: "Safety Rate", value: "99%", icon: Zap }
];

export default function AboutUs() {
    const { t } = useLanguage();
    return (
        <div className="flex flex-col min-h-screen bg-white dark:bg-zinc-950">
            {/* Hero Section */}
            <section className="relative py-32 bg-[#EFF6FF] dark:bg-zinc-950 overflow-hidden border-b border-sky-100 dark:border-zinc-800">
                <div className="absolute inset-0 bg-gradient-to-b from-[#EFF6FF] to-white dark:from-zinc-900/50 dark:to-transparent" />
                <div className="max-w-4xl mx-auto px-6 relative z-10 text-center">
                    <Badge variant="outline" className="text-blue-600 dark:text-slate-300 border-blue-200 dark:border-zinc-800 mb-8 px-4 py-1.5 bg-white/70 dark:bg-zinc-900/50 backdrop-blur-md rounded-full font-medium text-[12px] shadow-sm">
                        {t('about_story_badge')}
                    </Badge>
                    <h1 className="text-5xl md:text-7xl lg:text-[76px] font-semibold text-sky-950 dark:text-white mb-8 tracking-tighter leading-[1.05]">
                        {t('about_empower_title')}
                    </h1>
                    <p className="text-[15px] md:text-[16px] text-blue-700/70 dark:text-slate-400 font-light max-w-2xl mx-auto leading-relaxed">
                        {t('about_medora_desc')}
                    </p>
                </div>
            </section>

            {/* Stats Section */}
            <section className="py-16 bg-zinc-50 dark:bg-zinc-900/20 border-y border-slate-100 dark:border-zinc-800">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-8">
                        {stats.map((stat, i) => (
                            <div key={i} className="text-center group">
                                <div className="text-4xl font-semibold text-slate-900 dark:text-white mb-2 tracking-tighter">{stat.value}</div>
                                <div className="text-slate-500 dark:text-slate-400 text-[13px] font-medium flex items-center justify-center gap-2">
                                    <stat.icon className="h-4 w-4 text-slate-400" />
                                    {stat.label}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Mission & Vision */}
            <section className="py-32">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="grid md:grid-cols-2 gap-16">
                        <div className="space-y-8">
                            <h2 className="text-3xl font-semibold text-slate-900 dark:text-white tracking-tight flex items-center gap-3">
                                <Target className="text-slate-900 dark:text-white" strokeWidth={1.5} />
                                {t('about_mission_title')}
                            </h2>
                            <p className="text-[15px] text-slate-600 dark:text-slate-400 leading-relaxed font-light">
                                {t('about_mission_desc')}
                            </p>
                            <Separator className="bg-slate-100 dark:bg-zinc-800" />
                            <div className="grid grid-cols-2 gap-8">
                                <div className="space-y-3">
                                    <div className="h-1 w-8 bg-slate-900 dark:bg-white rounded-full" />
                                    <p className="font-semibold text-slate-900 dark:text-white text-[13px]">Accessibility</p>
                                    <p className="text-[13px] text-slate-500 dark:text-slate-400 font-light leading-relaxed">Connecting patients from all 58 provinces to clinical-grade medical safety.</p>
                                </div>
                                <div className="space-y-3">
                                    <div className="h-1 w-8 bg-slate-300 dark:bg-zinc-700 rounded-full" />
                                    <p className="font-semibold text-slate-900 dark:text-white text-[13px]">Innovation</p>
                                    <p className="text-[13px] text-slate-500 dark:text-slate-400 font-light leading-relaxed">Using advanced algorithms to ensure perfect safety checks, instantly.</p>
                                </div>
                            </div>
                        </div>

                        <div className="relative rounded-[28px] overflow-hidden bg-slate-900 dark:bg-zinc-900 p-12 flex flex-col justify-center text-white min-h-[400px]">
                            <div className="absolute top-0 right-0 p-8 opacity-5">
                                <Stethoscope size={160} className="text-white" />
                            </div>
                            <h2 className="text-3xl font-semibold mb-6 tracking-tight relative z-10">{t('about_vision_title')}</h2>
                            <p className="text-[16px] text-white/80 mb-10 leading-relaxed font-light italic relative z-10">
                                "{t('about_vision_desc')}"
                            </p>
                            <div className="flex items-center gap-3 relative z-10">
                                <div className="h-8 w-8 rounded-full bg-white/10 flex items-center justify-center">
                                    <Heart className="text-white h-4 w-4" />
                                </div>
                                <span className="font-medium text-[13px] text-white">Driven by Growth</span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Team Section */}
            <section className="py-24 bg-slate-50 dark:bg-zinc-900/20 border-t border-slate-100 dark:border-zinc-800">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="flex flex-col md:flex-row md:items-end justify-between mb-16 gap-6">
                        <div className="space-y-4">
                            <h2 className="text-4xl font-semibold text-slate-900 dark:text-white tracking-tighter">The Makers of Medora</h2>
                            <p className="text-slate-500 dark:text-slate-400 text-[15px] font-light max-w-xl leading-relaxed">
                                Our diverse team combines medical expertise with world-class engineering
                                to build a platform that truly serves the health of all Algerians.
                            </p>
                        </div>
                        <Link to="/register">
                            <Button variant="outline" className="rounded-[12px] font-medium text-[13.5px] px-6 h-10 group border-slate-200 dark:border-zinc-800 hover:bg-slate-100 dark:hover:bg-zinc-800 dark:text-white transition-all shadow-sm">
                                Join Our Mission
                                <ArrowRight className="ml-2 h-4 w-4 text-slate-400 group-hover:text-slate-900 dark:group-hover:text-white group-hover:translate-x-0.5 transition-all" />
                            </Button>
                        </Link>
                    </div>

                    <div className="grid md:grid-cols-3 gap-6">
                        {team.map((member, i) => (
                            <Card key={i} className="border border-slate-100 dark:border-zinc-800 shadow-sm hover:shadow-md transition-all duration-300 rounded-[24px] bg-white dark:bg-zinc-950 overflow-hidden group">
                                <CardHeader className="p-8 pb-4">
                                    <Avatar className="h-16 w-16 mb-5 ring-1 ring-slate-100 dark:ring-zinc-800 group-hover:ring-slate-200 dark:group-hover:ring-zinc-700 transition-all">
                                        <AvatarFallback className="bg-slate-50 dark:bg-zinc-900 text-slate-900 dark:text-white font-medium text-lg">
                                            {member.initials}
                                        </AvatarFallback>
                                    </Avatar>
                                    <div className="space-y-2">
                                        <Badge variant="secondary" className="bg-slate-50 dark:bg-zinc-900 text-slate-500 dark:text-slate-400 border-none px-2.5 py-0.5 font-medium text-[11px] mb-1">
                                            {member.tag}
                                        </Badge>
                                        <CardTitle className="text-[17px] font-semibold text-slate-900 dark:text-white tracking-tight">{member.name}</CardTitle>
                                        <CardDescription className="text-slate-500 dark:text-slate-400 font-medium text-[13px]">
                                            {member.role}
                                        </CardDescription>
                                    </div>
                                </CardHeader>
                                <CardContent className="p-8 pt-2">
                                    <p className="text-slate-500 dark:text-slate-400 leading-relaxed text-[13.5px] font-light">
                                        {member.bio}
                                    </p>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </div>
            </section>

            {/* Final CTA */}
            <section className="py-32 max-w-7xl mx-auto px-6">
                <div className="bg-[#061225] rounded-[28px] p-12 md:p-20 text-center text-white relative overflow-hidden shadow-2xl border border-blue-400/10">
                    <div className="absolute inset-0 bg-gradient-to-b from-blue-500/10 to-transparent" />
                    <div className="relative z-10">
                        <h2 className="text-4xl md:text-[44px] font-semibold mb-6 tracking-tighter leading-[1.1]">
                            Ready to check your medications?
                        </h2>
                        <p className="text-white/70 text-[15px] font-light mb-10 max-w-xl mx-auto leading-relaxed">
                            Join the fastest-growing health safety community in Algeria and protect your family today.
                        </p>
                        <div className="flex flex-wrap justify-center gap-4">
                            <Link to="/interactions">
                                <Button className="bg-white hover:bg-slate-100 text-slate-900 px-8 h-12 rounded-[12px] font-medium text-[14.5px] shadow-xl active:scale-[0.98] transition-all">
                                    Check Interactions
                                </Button>
                            </Link>
                            <Link to="/register">
                                <Button variant="outline" className="border-white/20 bg-white/5 text-white hover:bg-white/10 px-8 h-12 rounded-[12px] font-medium text-[14.5px] active:scale-[0.98] transition-all">
                                    Join Medora
                                </Button>
                            </Link>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    );
}

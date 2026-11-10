import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Link } from "react-router-dom";
import { ArrowRight, ArrowUpRight, ShieldCheck, Activity, Languages, Stethoscope, FileText, Sparkles, ChevronRight, ScanLine, BookOpen, Users, Heart, Building2 } from "lucide-react";
import { motion } from "framer-motion";
import { useLanguage } from "../contexts/LanguageContext";

import imgStethoscope from "@/assets/etactics-inc-g3PsF4_y7ZY-unsplash.jpg";
import imgNurse from "@/assets/jeshoots-com-l0j0DHVWcIE-unsplash.jpg";
import imgPillsSpilling from "@/assets/towfiqu-barbhuiya-w8p9cQDLX7I-unsplash.jpg";
import imgLabScientist from "@/assets/benjamin-lehman-gkZ-k3xf25w-unsplash.jpg";
import imgPillOrganizer from "@/assets/towfiqu-barbhuiya-_04ev82q-s0-unsplash.jpg";
import imgBlisterPacks from "@/assets/roberto-sorin-RS0-h_pyByk-unsplash.jpg";
import imgGlovesHeart from "@/assets/anton-8q-U8X1zkvI-unsplash.jpg";

const fade = {
    hidden: { opacity: 0, y: 20 },
    show: (d = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.8, delay: d * 0.15, ease: "easeOut" } }),
};

function Home() {
    const { t } = useLanguage();
    return (
        <div className="w-full bg-white dark:bg-zinc-950 font-sans">

            {/* ────────────── INTRO ────────────── */}
            <section className="relative h-screen min-h-[600px] flex flex-col justify-center overflow-hidden">
                {/* BG image */}
                <div className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: `url(${imgBlisterPacks})` }} />
                
                {/* Dark overlay & Upward Gradient Shadow */}
                <div className="absolute inset-0 bg-black/30" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent" />

                {/* Content */}
                <div className="relative z-10 w-full max-w-4xl mx-auto px-6 text-center -mt-10">
                    <motion.h1
                        variants={fade} initial="hidden" animate="show" custom={0}
                        className="text-5xl md:text-7xl lg:text-[76px] font-semibold tracking-tighter text-white leading-[1.05] mb-6 drop-shadow-2xl"
                        style={{ textShadow: "0 4px 20px rgba(0,0,0,0.6)" }}
                    >
                        {t('hero_title')}
                    </motion.h1>

                    <motion.p
                        variants={fade} initial="hidden" animate="show" custom={1}
                        className="text-[15px] md:text-[16px] text-white/90 max-w-2xl mx-auto mb-10 font-light leading-relaxed drop-shadow-xl"
                        style={{ textShadow: "0 2px 10px rgba(0,0,0,0.8)" }}
                    >
                        {t('hero_desc')}
                    </motion.p>

                    <motion.div
                        variants={fade} initial="hidden" animate="show" custom={2}
                        className="flex justify-center"
                    >
                        <Link to="/interactions">
                            <button className="h-11 px-8 rounded-full bg-white text-zinc-900 font-semibold text-[13px] hover:bg-zinc-100 transition-all flex items-center gap-2 shadow-2xl hover:scale-105">
                                {t('try_medora')} <ArrowUpRight className="w-4 h-4 text-zinc-600" strokeWidth={2.5} />
                            </button>
                        </Link>
                    </motion.div>
                </div>

            </section>


            {/* ────────────── HOW IT WORKS ────────────── */}
            <section className="py-24 lg:py-32 bg-slate-50/50 dark:bg-zinc-900/20 border-t border-slate-100 dark:border-zinc-800">
                <div className="max-w-7xl mx-auto px-6">
                    
                    {/* Header: Title left, Subtitle right */}
                    <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 mb-16 lg:mb-24">
                        <motion.h2 
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            className="text-4xl md:text-5xl font-semibold tracking-tight text-slate-900 dark:text-white leading-[1.1] max-w-md"
                        >
                            {t('effortless_safety')}
                        </motion.h2>
                        <motion.p 
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: 0.1 }}
                            className="text-[15px] text-slate-600 max-w-sm leading-relaxed"
                        >
                            {t('seamless_exp')}
                        </motion.p>
                    </div>

                    {/* Content Grid */}
                    <div className="flex flex-col lg:flex-row items-center justify-between gap-8 lg:gap-12">
                        
                        {/* Left Column (Steps 1 & 2) */}
                        <div className="flex-1 w-full flex flex-col gap-6 lg:gap-8">
                            <motion.div 
                                initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}
                                className="bg-white dark:bg-zinc-950 border border-slate-200/60 dark:border-zinc-800 rounded-3xl p-8 lg:p-10 shadow-sm hover:shadow-md transition-all"
                            >
                                <p className="text-[15px] font-semibold text-slate-900 dark:text-slate-300 italic mb-6">01</p>
                                <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-3">{t('step1_title')}</h3>
                                <p className="text-[15px] text-slate-600 leading-relaxed">{t('step1_desc')}</p>
                            </motion.div>
                            
                            <motion.div 
                                initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }}
                                className="bg-white dark:bg-zinc-950 border border-slate-200/60 dark:border-zinc-800 rounded-3xl p-8 lg:p-10 shadow-sm hover:shadow-md transition-all"
                            >
                                <p className="text-[15px] font-semibold text-slate-900 dark:text-slate-300 italic mb-6">02</p>
                                <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-3">{t('step2_title')}</h3>
                                <p className="text-[15px] text-slate-600 leading-relaxed">{t('step2_desc')}</p>
                            </motion.div>
                        </div>

                        {/* Middle Column (Tall Image) */}
                        <motion.div 
                            initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.3 }}
                            className="w-full lg:w-[380px] xl:w-[420px] shrink-0 h-[500px] lg:h-[650px] rounded-[32px] overflow-hidden shadow-2xl relative"
                        >
                            <img src={imgStethoscope} alt="Medora checking process" className="w-full h-full object-cover" />
                            <div className="absolute inset-0 bg-black/5" />
                        </motion.div>

                        {/* Right Column (Steps 3 & 4) */}
                        <div className="flex-1 w-full flex flex-col gap-6 lg:gap-8">
                            <motion.div 
                                initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: 0.4 }}
                                className="bg-white dark:bg-zinc-950 border border-slate-200/60 dark:border-zinc-800 rounded-3xl p-8 lg:p-10 shadow-sm hover:shadow-md transition-all"
                            >
                                <p className="text-[15px] font-semibold text-slate-900 dark:text-slate-300 italic mb-6">03</p>
                                <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-3">{t('step3_title')}</h3>
                                <p className="text-[15px] text-slate-600 leading-relaxed">{t('step3_desc')}</p>
                            </motion.div>
                            
                            <motion.div 
                                initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: 0.5 }}
                                className="bg-white dark:bg-zinc-950 border border-slate-200/60 dark:border-zinc-800 rounded-3xl p-8 lg:p-10 shadow-sm hover:shadow-md transition-all"
                            >
                                <p className="text-[15px] font-semibold text-slate-900 dark:text-slate-300 italic mb-6">04</p>
                                <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-3">{t('step4_title')}</h3>
                                <p className="text-[15px] text-slate-600 leading-relaxed">{t('step4_desc')}</p>
                            </motion.div>
                        </div>

                    </div>
                </div>
            </section>


            {/* ────────────── WHO IS MEDORA FOR ────────────── */}
            <section className="py-24 md:py-32 bg-[#f4f4f5] dark:bg-zinc-900 flex justify-center border-t border-slate-100 dark:border-zinc-800">
                <div className="w-full max-w-[1150px] px-6 md:px-10">
                    
                    {/* Header Row */}
                    <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-10 lg:gap-24 mb-16 md:mb-20">
                        <h2 className="text-4xl md:text-[46px] font-semibold tracking-tight text-slate-900 dark:text-white leading-[1.25] lg:w-1/2">
                            {t('intel_safety')}
                        </h2>
                        <p className="text-[13.5px] text-[#4a4a4a] dark:text-slate-400 leading-[1.8] font-normal lg:w-1/2">
                            {t('intel_safety_desc')}
                        </p>
                    </div>

                    {/* Cards Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
                        {/* Card 1 */}
                        <div className="bg-white dark:bg-zinc-950 border border-slate-100 dark:border-zinc-800 rounded-[28px] p-8 pb-10 shadow-[0_8px_30px_rgba(0,0,0,0.04)] hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-start cursor-pointer">
                            <div className="w-[52px] h-[52px] bg-[#0B0D17] rounded-[16px] flex items-center justify-center mb-8 shrink-0">
                                <Heart className="w-[22px] h-[22px] text-white" strokeWidth={2.5} />
                            </div>
                            <h3 className="text-[18px] font-semibold text-slate-900 dark:text-white mb-3 tracking-tight">{t('card_patients_title')}</h3>
                            <p className="text-[13.5px] text-slate-500 dark:text-slate-400 leading-[1.7] font-normal">
                                {t('card_patients_1')} {t('card_patients_2')}
                            </p>
                        </div>

                        {/* Card 2 */}
                        <div className="bg-white dark:bg-zinc-950 border border-slate-100 dark:border-zinc-800 rounded-[28px] p-8 pb-10 shadow-[0_8px_30px_rgba(0,0,0,0.04)] hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-start cursor-pointer">
                            <div className="w-[52px] h-[52px] bg-[#0B0D17] rounded-[16px] flex items-center justify-center mb-8 shrink-0">
                                <Stethoscope className="w-[22px] h-[22px] text-white" strokeWidth={2.5} />
                            </div>
                            <h3 className="text-[18px] font-semibold text-slate-900 dark:text-white mb-3 tracking-tight">{t('card_pharm_title')}</h3>
                            <p className="text-[13.5px] text-slate-500 dark:text-slate-400 leading-[1.7] font-normal">
                                {t('card_pharm_1')} {t('card_pharm_2')} {t('card_pharm_3')}
                            </p>
                        </div>

                        {/* Card 3 */}
                        <div className="bg-white dark:bg-zinc-950 border border-slate-100 dark:border-zinc-800 rounded-[28px] p-8 pb-10 shadow-[0_8px_30px_rgba(0,0,0,0.04)] hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-start cursor-pointer">
                            <div className="w-[52px] h-[52px] bg-[#0B0D17] rounded-[16px] flex items-center justify-center mb-8 shrink-0">
                                <Building2 className="w-[22px] h-[22px] text-white" strokeWidth={2.5} />
                            </div>
                            <h3 className="text-[18px] font-semibold text-slate-900 dark:text-white mb-3 tracking-tight">{t('card_system_title')}</h3>
                            <p className="text-[13.5px] text-slate-500 dark:text-slate-400 leading-[1.7] font-normal">
                                {t('card_system_1')} {t('card_system_2')}
                            </p>
                        </div>
                    </div>
                </div>
            </section>


            {/* ────────────── TESTIMONIALS ────────────── */}
            <section className="py-24 bg-white dark:bg-zinc-950 overflow-hidden border-t border-slate-100 dark:border-zinc-800">
                <div className="w-full max-w-[1300px] mx-auto px-6">
                    <h2 className="text-4xl md:text-[42px] font-medium text-center text-slate-900 dark:text-white mb-16 tracking-tight">
                        {t('testimonials_title')}
                    </h2>

                    <div className="flex items-center justify-center gap-6 lg:gap-12">
                        
                        {/* Left Card (Inactive) */}
                        <div className="relative hidden md:block">
                            <button className="absolute top-10 -right-8 lg:-right-12 z-10 w-[52px] h-[52px] bg-black dark:bg-white rounded-full flex items-center justify-center hover:scale-105 transition-transform shadow-xl">
                                <ArrowRight className="w-5 h-5 text-white dark:text-black rotate-180" />
                            </button>
                            
                            <div className="w-[260px] h-[300px] rounded-[40px] border-[14px] border-slate-100 dark:border-zinc-800 overflow-hidden shrink-0 mt-6">
                                <img src={imgLabScientist} alt="Pharmacist" className="w-full h-full object-cover" />
                            </div>
                        </div>

                        {/* Center Card (Active) */}
                        <div className="bg-[#eef2ff] dark:bg-indigo-950/30 rounded-[40px] p-3 flex flex-col sm:flex-row gap-6 w-full max-w-[650px] shadow-sm shrink-0 relative z-20">
                            {/* Image */}
                            <div className="w-full sm:w-[280px] h-[340px] rounded-[32px] overflow-hidden shrink-0">
                                <img src={imgNurse} alt="Dr. Amina" className="w-full h-full object-cover object-top" />
                            </div>
                            
                            {/* Content */}
                            <div className="flex-1 py-8 pr-8 flex flex-col">
                                <div className="mb-5">
                                    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                        <path d="M10 11V18H4V11H7C7 8.79086 5.20914 7 3 7V4C6.86599 4 10 7.13401 10 11ZM20 11V18H14V11H17C17 8.79086 15.2091 7 13 7V4C16.866 4 20 7.13401 20 11Z" fill="#c7d2fe" className="dark:fill-indigo-900"/>
                                    </svg>
                                </div>
                                <p className="text-[13.5px] text-indigo-950 dark:text-indigo-200 leading-[1.8] mb-8 font-medium">
                                    {t('dr_amina_quote')}
                                </p>
                                <div className="mt-auto">
                                    <h4 className="font-bold text-indigo-950 dark:text-white text-[15px] tracking-tight">Dr. Amina</h4>
                                    <p className="text-[13px] text-indigo-800/70 dark:text-indigo-300/70 font-semibold mt-0.5">Clinical Pharmacist</p>
                                </div>
                            </div>
                        </div>

                        {/* Right Card (Inactive) */}
                        <div className="relative hidden lg:block">
                            <div className="w-[260px] h-[300px] rounded-[40px] border-[14px] border-blue-50 dark:border-blue-900/20 overflow-hidden shrink-0 mb-6">
                                <img src={imgPillOrganizer} alt="Patient" className="w-full h-full object-cover" />
                            </div>
                            
                            <button className="absolute bottom-10 -left-8 lg:-left-12 z-10 w-[52px] h-[52px] bg-black dark:bg-white rounded-full flex items-center justify-center hover:scale-105 transition-transform shadow-xl">
                                <ArrowRight className="w-5 h-5 text-white dark:text-black" />
                            </button>
                        </div>

                    </div>
                </div>
            </section>


            {/* ────────────── CTA ────────────── */}
            <section className="relative h-[600px] flex items-center justify-center overflow-hidden border-t border-slate-100 dark:border-zinc-800">
                <div
                    className="absolute inset-0 bg-cover bg-center scale-105"
                    style={{
                        backgroundImage: `url(${imgGlovesHeart})`,
                        backgroundPosition: 'center 40%'
                    }}
                />
                {/* Refined gradient overlay for better text readability */}
                <div className="absolute inset-0 bg-gradient-to-t from-slate-900/90 via-slate-900/60 to-slate-900/40" />

                <div className="relative z-10 w-full">
                    <div className="max-w-3xl mx-auto text-center px-6">
                        <motion.h2 
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            className="text-4xl md:text-[52px] font-medium tracking-tight text-white leading-[1.15] mb-6"
                        >
                            {t('ready_to_verify')}
                        </motion.h2>
                        
                        <motion.p 
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: 0.1 }}
                            className="text-[15px] md:text-[16px] text-slate-200 font-light leading-relaxed mb-10 max-w-xl mx-auto"
                        >
                            {t('join_thousands')}
                        </motion.p>
                        
                        <motion.div 
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: 0.2 }}
                            className="flex flex-col sm:flex-row justify-center gap-4"
                        >
                            <Link to="/interactions">
                                <button className="w-full sm:w-auto bg-white text-slate-900 rounded-[12px] px-8 py-3.5 text-[14.5px] font-medium hover:bg-slate-100 transition-all active:scale-[0.98] shadow-lg">
                                    {t('try_medora')}
                                </button>
                            </Link>
                            <Link to="/register">
                                <button className="w-full sm:w-auto bg-white/5 border border-white/20 text-white rounded-[12px] px-8 py-3.5 text-[14.5px] font-medium backdrop-blur-md hover:bg-white/10 transition-all active:scale-[0.98]">
                                    {t('create_account')}
                                </button>
                            </Link>
                        </motion.div>
                    </div>
                </div>
            </section>

            {/* ────────────── CONTACT US ────────────── */}
            <section className="py-16 md:py-20 bg-white dark:bg-zinc-950 flex justify-center">
                <div className="w-full max-w-[700px] px-4 md:px-6">
                    <div className="bg-[#fafafa] dark:bg-zinc-900/20 border border-slate-100 dark:border-zinc-800 rounded-[24px] p-8 md:p-10">
                        
                        <h2 className="text-2xl md:text-3xl font-medium tracking-tight text-slate-900 dark:text-white mb-6">
                            {t('reach_out')}
                        </h2>

                        <div className="flex flex-col gap-3">
                            <input 
                                type="text" 
                                placeholder={t('full_name')}
                                className="w-full bg-white dark:bg-zinc-950 border border-slate-200/80 dark:border-zinc-800 rounded-lg px-4 py-2.5 text-[13px] text-slate-900 dark:text-white placeholder:text-slate-500 outline-none focus:border-slate-300 transition-all" 
                            />
                            <input 
                                type="email" 
                                placeholder={t('email_addr')}
                                className="w-full bg-white dark:bg-zinc-950 border border-slate-200/80 dark:border-zinc-800 rounded-lg px-4 py-2.5 text-[13px] text-slate-900 dark:text-white placeholder:text-slate-500 outline-none focus:border-slate-300 transition-all" 
                            />
                            <input 
                                type="tel" 
                                placeholder={t('phone_num')} 
                                className="w-full md:w-[45%] bg-white dark:bg-zinc-950 border border-slate-200/80 dark:border-zinc-800 rounded-lg px-4 py-2.5 text-[13px] text-slate-900 dark:text-white placeholder:text-slate-500 outline-none focus:border-slate-300 transition-all" 
                            />
                            <textarea 
                                placeholder={t('how_can_help')} 
                                rows={4}
                                className="w-full bg-white dark:bg-zinc-950 border border-slate-200/80 dark:border-zinc-800 rounded-lg px-4 py-3 text-[13px] text-slate-900 dark:text-white placeholder:text-slate-500 outline-none focus:border-slate-300 transition-all resize-none mt-1" 
                            ></textarea>

                            <div className="mt-2 text-[11px] text-[#8c8c8c] leading-relaxed font-light">
                                <p className="mb-3">
                                    By submitting this form, I agree to receiving customer care and marketing SMS messages from Medora. <br className="hidden md:block" /> Message and data rates may apply. Reply STOP to opt out, Reply HELP for help.
                                </p>
                                <p className="text-[#8c8c8c]">
                                    {t('privacy_terms')}
                                </p>
                            </div>
                            
                            <div className="mt-1">
                                <button type="button" className="bg-slate-900 dark:bg-white text-white dark:text-zinc-900 rounded-lg px-6 py-2.5 text-[13px] font-medium hover:bg-slate-800 dark:hover:bg-slate-200 transition-all active:scale-[0.98] w-full md:w-auto shadow-sm">
                                    {t('submit_req')}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    );
}

export default Home;

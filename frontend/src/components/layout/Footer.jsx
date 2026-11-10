import { Link } from "react-router-dom";

export default function Footer() {
    return (
        <footer className="bg-[#fafafa] dark:bg-zinc-900/40 pt-16 pb-8 border-t border-slate-100 dark:border-zinc-800 transition-colors">
            <div className="max-w-7xl mx-auto px-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-12 text-[13px]">
                    <div className="space-y-4">
                        <Link to="/" className="flex items-center gap-0.5 hover:opacity-80 transition-opacity w-fit">
                            <span className="text-xl font-bold tracking-tighter text-slate-900 dark:text-white">Medora</span>
                            <span className="text-2xl leading-none -mt-1 text-slate-900 dark:text-white">.</span>
                        </Link>
                        <p className="leading-relaxed text-slate-500 dark:text-slate-400 font-light">
                            Empowering Algerian patients and pharmacists with clinical-grade drug interaction analysis. Explained in Darija for absolute clarity.
                        </p>
                    </div>

                    <div>
                        <h3 className="text-slate-900 dark:text-white font-medium mb-5 text-[14px]">Platform</h3>
                        <ul className="space-y-3 text-slate-500 dark:text-slate-400 font-light">
                            <li><Link to="/interactions" className="hover:text-slate-900 dark:hover:text-white transition-colors">Interaction Checker</Link></li>
                            <li><Link to="/pharmacist" className="hover:text-slate-900 dark:hover:text-white transition-colors">Pharmacist Portal</Link></li>
                            <li><Link to="/" className="hover:text-slate-900 dark:hover:text-white transition-colors">How it Works</Link></li>
                            <li><Link to="/register" className="hover:text-slate-900 dark:hover:text-white transition-colors">Join Now</Link></li>
                        </ul>
                    </div>

                    <div>
                        <h3 className="text-slate-900 dark:text-white font-medium mb-5 text-[14px]">Resources</h3>
                        <ul className="space-y-3 text-slate-500 dark:text-slate-400 font-light">
                            <li><Link to="/ddinter" className="hover:text-slate-900 dark:hover:text-white transition-colors">DDInter Database</Link></li>
                            <li><Link to="/faq" className="hover:text-slate-900 dark:hover:text-white transition-colors">FAQs</Link></li>
                            <li><Link to="/support" className="hover:text-slate-900 dark:hover:text-white transition-colors">Support Center</Link></li>
                            <li><Link to="/privacy" className="hover:text-slate-900 dark:hover:text-white transition-colors">Privacy Policy</Link></li>
                        </ul>
                    </div>

                    <div>
                        <h3 className="text-slate-900 dark:text-white font-medium mb-5 text-[14px]">Contact Us</h3>
                        <ul className="space-y-3 text-slate-500 dark:text-slate-400 font-light">
                            <li>Email: <a href="mailto:support@medsafe.dz" className="hover:text-slate-900 dark:hover:text-white transition-colors">support@medsafe.dz</a></li>
                            <li>Phone: <span>+213 21 00 00 00</span></li>
                            <li>Address: <span>Algiers, Algeria</span></li>
                        </ul>
                    </div>
                </div>

                <div className="mt-16 pt-8 border-t border-slate-100 dark:border-zinc-800 flex flex-col md:flex-row items-center justify-between gap-4 text-[12px] font-light text-slate-400 dark:text-slate-500">
                    <p>© 2026 Medora — Axis 3 Pharmatech Innovation. All rights reserved.</p>
                    <div className="flex gap-6">
                        <Link to="/terms" className="hover:text-slate-900 dark:hover:text-white transition-colors">Terms of Service</Link>
                        <Link to="/privacy" className="hover:text-slate-900 dark:hover:text-white transition-colors">Privacy Policy</Link>
                    </div>
                </div>
            </div>
        </footer>
    );
}

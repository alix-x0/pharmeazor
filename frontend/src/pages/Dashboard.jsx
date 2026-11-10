import React from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription
} from "@/components/ui/card";
import {
  Users,
  TrendingUp,
  Activity,
  Database,
  AlertCircle,
  ChevronRight,
  LayoutDashboard,
  Stethoscope,
  ArrowUpRight
} from "lucide-react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid
} from "recharts";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { useNavigate } from 'react-router-dom';
import { useLanguage } from "../contexts/LanguageContext";

const data = [
  { name: "Mon", scans: 45, alerts: 12 },
  { name: "Tue", scans: 52, alerts: 8 },
  { name: "Wed", scans: 48, alerts: 15 },
  { name: "Thu", scans: 61, alerts: 10 },
  { name: "Fri", scans: 55, alerts: 14 },
  { name: "Sat", scans: 32, alerts: 5 },
  { name: "Sun", scans: 38, alerts: 7 },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const { t } = useLanguage();

  const statsList = [
    { title: t('totalScans'), value: "1,284", icon: Activity, trend: "+12%", color: "text-blue-600", bg: "bg-blue-50" },
    { title: t('criticalAlerts'), value: "42", icon: AlertCircle, trend: "-5%", color: "text-red-600", bg: "bg-red-50" },
    { title: t('activePharmacists'), value: "18", icon: Users, trend: "+2", color: "text-emerald-600", bg: "bg-emerald-50" },
    { title: t('databaseStatus'), value: t('live'), icon: Database, trend: t('stable'), color: "text-zinc-600", bg: "bg-zinc-50" },
  ];

  return (
    <motion.div
      className="flex flex-col gap-6 w-full pb-8 pt-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      {/* ─── Header ─── */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-zinc-100 dark:border-zinc-800 pb-6">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50 flex items-center gap-2">
            <LayoutDashboard className="w-6 h-6 text-primary" />
            {t('clinicalDashboard')}
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            {t('realTimeAnalytics')}
          </p>
        </div>

        <Button
          onClick={() => navigate('/dashboard/pharmacist')}
          className="gap-2 h-11 px-6 rounded-xl font-bold shadow-lg shadow-primary/20 active:scale-95 transition-all"
        >
          <Stethoscope className="w-4 h-4" />
          {t('launchPharmacistMode')}
        </Button>
      </div>

      {/* ─── Stats ─── */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {statsList.map((stat, i) => (
          <Card key={i} className="border-zinc-200 dark:border-zinc-800 shadow-sm transition-all hover:shadow-md">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-xs font-semibold text-slate-400 dark:text-zinc-400 uppercase tracking-widest">
                {stat.title}
              </CardTitle>
              <stat.icon className={`h-4 w-4 ${stat.color}`} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-sky-950 dark:text-zinc-50 font-sans tracking-tighter">{stat.value}</div>
              <p className="text-[11px] text-slate-400 dark:text-zinc-400 mt-1 flex items-center font-light">
                <span className="text-blue-600 dark:text-emerald-400 mr-1 font-semibold">{stat.trend}</span>
                {t('vsLastWeek')}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 grid-cols-1 lg:grid-cols-7">
        {/* Main Chart */}
        <Card className="col-span-full lg:col-span-4 border-blue-100/50 dark:border-zinc-800 shadow-sm rounded-[24px] overflow-hidden bg-white/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-xl font-bold text-sky-950 tracking-tight">{t('interactionTrends')}</CardTitle>
            <CardDescription>{t('scanVolumeDescription')}</CardDescription>
          </CardHeader>
          <CardContent className="pl-2">
            <div className="h-[300px] w-full mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data}>
                  <defs>
                    <linearGradient id="colorScans" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#2563eb" stopOpacity={0.1}/>
                      <stop offset="95%" stopColor="#2563eb" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis 
                    dataKey="name" 
                    axisLine={false} 
                    tickLine={false} 
                    tick={{fill: '#94a3b8', fontSize: 12}}
                    dy={10}
                  />
                  <YAxis 
                    axisLine={false} 
                    tickLine={false} 
                    tick={{fill: '#94a3b8', fontSize: 12}}
                  />
                  <Tooltip 
                    contentStyle={{borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)'}}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="scans" 
                    stroke="#2563eb" 
                    strokeWidth={3}
                    fillOpacity={1} 
                    fill="url(#colorScans)" 
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Recent Activity / Status */}
        <Card className="col-span-full lg:col-span-3 border-zinc-200 dark:border-zinc-800 shadow-sm rounded-[24px] bg-white/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-lg font-bold text-sky-950 tracking-tight">{t('facilityStatus')}</CardTitle>
            <CardDescription>{t('activeStationsDescription')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {[
                { station: "Pharmacy A", status: "Online", scans: "242" },
                { station: "Pharmacy B", status: "Online", scans: "189" },
                { station: "Emergency", status: "Maintenance", scans: "42" },
              ].map((item, i) => (
                <div key={i} className="flex items-center group cursor-pointer border-b border-zinc-50 dark:border-zinc-800/50 pb-4 last:border-0 last:pb-0">
                  <div className={`w-2 h-2 rounded-full mr-4 ${item.status === 'Online' ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]' : 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.4)]'}`} />
                  <div className="flex-1">
                    <p className="text-sm font-bold text-zinc-900 dark:text-zinc-50 tracking-tight">{item.station}</p>
                    <p className="text-[11px] text-zinc-500 font-medium uppercase tracking-wider mt-0.5">{item.status} • {item.scans} SCANS</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-zinc-300 group-hover:text-primary transition-all group-hover:translate-x-0.5" />
                </div>
              ))}
            </div>
            <Button variant="outline" className="w-full mt-6 text-xs font-semibold text-zinc-500 h-9 rounded-lg group">
              View Detailed Analytics
              <ArrowUpRight className="ml-2 w-3 h-3 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </Button>
          </CardContent>
        </Card>
      </div>
    </motion.div>
  );
}

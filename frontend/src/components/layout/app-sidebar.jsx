"use client"

import * as React from "react"
import { useNavigate } from "react-router-dom"
import {
  GalleryVerticalEnd,
  LayoutDashboard,
  Settings2,
  Search,
  Stethoscope,
  Activity,
  ShieldCheck,
  FileText,
  Database,
  GraduationCap,
} from "lucide-react"

import { NavMain } from "@/components/layout/nav-main"
import { NavUser } from "@/components/layout/nav-user"
import { TeamSwitcher } from "@/components/layout/team-switcher"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
  SidebarGroup,
  SidebarGroupContent,
} from "@/components/ui/sidebar"
import api from "@/api/api"
import { ACCESS_TOKEN } from "@/constants"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"

const data = {
  teams: [
    {
      name: "Medora",
      logo: ShieldCheck,
      plan: "Clinical Platform",
    },
  ],
  navMain: [
    {
      title: "Dashboard",
      url: "/dashboard",
      icon: LayoutDashboard,
      isActive: true,
      items: [
        {
          title: "Overview",
          url: "/dashboard",
        },
        {
          title: "Analytics",
          url: "/dashboard/analytics",
        },
      ],
    },
    {
      title: "Interactions",
      url: "/interactions",
      icon: Activity,
      items: [
        {
          title: "Check Interactions",
          url: "/interactions",
        },
      ],
    },
    {
      title: "Pharmacist Mode",
      url: "/dashboard/pharmacist",
      icon: Stethoscope,
      items: [
        {
          title: "Clinical Suite",
          url: "/dashboard/pharmacist",
        },
      ],
    },
    {
      title: "PharmaTutor",
      url: "/dashboard/tutor",
      icon: GraduationCap,
      items: [
        {
          title: "Training Chat",
          url: "/dashboard/tutor",
        },
      ],
    },
    {
      title: "Platform",
      url: "#",
      icon: Settings2,
      items: [
        {
          title: "Settings",
          url: "/settings",
        },
      ],
    },
  ],
}

export function AppSidebar({ ...props }) {
  const [userInfo, setUserInfo] = React.useState(null)
  const navigate = useNavigate()

  React.useEffect(() => {
    const fetchProfile = async () => {
      try {
        const token = localStorage.getItem(ACCESS_TOKEN)
        if (token) {
          const res = await api.get("/auth/profile/")
          setUserInfo(res.data)
        }
      } catch (error) {
        console.error("Failed to fetch profile:", error)
      }
    }
    fetchProfile()
  }, [])

  const handleLogout = () => {
    localStorage.clear()
    navigate("/login")
  }

  return (
    <Sidebar variant="inset" collapsible="icon" {...props}>
      <SidebarHeader>
        <TeamSwitcher teams={data.teams} />
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup className="py-0 group-data-[collapsible=icon]:hidden">
          <SidebarGroupContent className="relative">
            <Label htmlFor="search" className="sr-only">
              Search
            </Label>
            <Input
              id="search"
              placeholder="Search..."
              className="pl-8 bg-sidebar-accent/50 border-none shadow-none h-9 mt-2"
            />
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 select-none opacity-50" />
          </SidebarGroupContent>
        </SidebarGroup>
        <NavMain items={data.navMain} />
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={userInfo} handleLogout={handleLogout} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}

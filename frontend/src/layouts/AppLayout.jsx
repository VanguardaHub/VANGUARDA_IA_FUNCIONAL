import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard, Users, Sparkles, Layers, BookOpen, Megaphone,
  ScrollText, Settings2, CreditCard, LogOut, Zap,
} from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
  { to: "/clientes", label: "Clientes", icon: Users, testid: "nav-clientes" },
  { to: "/gerar", label: "Gerar Peça", icon: Sparkles, testid: "nav-gerar" },
  { to: "/pecas", label: "Peças", icon: Layers, testid: "nav-pecas" },
  { to: "/biblia", label: "Bíblia", icon: BookOpen, testid: "nav-biblia" },
  { to: "/campanhas", label: "Campanhas", icon: Megaphone, testid: "nav-campanhas" },
  { to: "/logs", label: "Logs & Alertas", icon: ScrollText, testid: "nav-logs" },
  { to: "/configuracoes", label: "Configurações", icon: Settings2, testid: "nav-configuracoes" },
  { to: "/planos", label: "Planos", icon: CreditCard, testid: "nav-planos" },
];

const PLAN_LABELS = { trial: "Trial", starter: "Starter", pro: "Pro", agency: "Enterprise" };

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  return (
    <div className="min-h-screen bg-[#0B0B0D] noise-overlay" data-testid="app-layout">
      <aside className="w-64 fixed left-0 top-0 h-screen border-r border-slate-800 bg-[#0E0E11] z-40 hidden lg:flex flex-col" data-testid="sidebar">
        <div className="h-16 flex items-center gap-3 px-6 border-b border-slate-800/60">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-red-500 to-rose-600 flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="font-display font-extrabold text-lg tracking-tight">Vanguarda<span className="text-red-400">.IA</span></span>
        </div>
        <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
          {NAV.map(({ to, label, icon: Icon, testid }) => (
            <NavLink
              key={to}
              to={to}
              data-testid={testid}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-200 ${
                  isActive
                    ? "bg-red-500/10 text-red-300 border border-red-500/20"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04] border border-transparent"
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-slate-800/60">
          <div className="glass-card p-3 flex items-center gap-3">
            <Avatar className="w-9 h-9">
              <AvatarImage src={user?.picture} />
              <AvatarFallback className="bg-red-600 text-white text-xs">
                {user?.name?.slice(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate" data-testid="sidebar-user-name">{user?.name}</p>
              <p className="text-xs text-red-400 font-mono" data-testid="sidebar-user-plan">{PLAN_LABELS[user?.plan] || user?.plan}</p>
            </div>
          </div>
        </div>
      </aside>

      <div className="lg:pl-64 flex flex-col min-h-screen">
        <header className="sticky top-0 z-30 h-16 backdrop-blur-xl bg-[#0B0B0D]/80 border-b border-slate-800/60 px-6 flex items-center justify-between" data-testid="app-header">
          <nav className="flex lg:hidden gap-1 overflow-x-auto">
            {NAV.map(({ to, icon: Icon, testid }) => (
              <NavLink key={to} to={to} data-testid={`${testid}-mobile`}
                className={({ isActive }) =>
                  `p-2 rounded-lg transition-colors ${isActive ? "bg-red-500/10 text-red-300" : "text-slate-400 hover:text-slate-200"}`
                }>
                <Icon className="w-5 h-5" />
              </NavLink>
            ))}
          </nav>
          <div className="hidden lg:block">
            <p className="text-xs text-slate-500 font-mono">vanguarda.ia / workspace</p>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger data-testid="user-menu-trigger" className="outline-none">
              <Avatar className="w-9 h-9 ring-2 ring-red-500/30 hover:ring-red-500/60 transition-all">
                <AvatarImage src={user?.picture} />
                <AvatarFallback className="bg-red-600 text-white text-xs">
                  {user?.name?.slice(0, 2).toUpperCase()}
                </AvatarFallback>
              </Avatar>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="bg-[#15151A] border-slate-800 text-slate-200 w-56">
              <DropdownMenuLabel>
                <p className="font-medium">{user?.name}</p>
                <p className="text-xs text-slate-500 font-normal">{user?.email}</p>
              </DropdownMenuLabel>
              <DropdownMenuSeparator className="bg-slate-800" />
              <DropdownMenuItem onClick={() => navigate("/planos")} className="cursor-pointer focus:bg-white/5" data-testid="menu-plans">
                <CreditCard className="w-4 h-4 mr-2" /> Planos & Assinatura
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate("/configuracoes")} className="cursor-pointer focus:bg-white/5" data-testid="menu-settings">
                <Settings2 className="w-4 h-4 mr-2" /> Configurações
              </DropdownMenuItem>
              <DropdownMenuSeparator className="bg-slate-800" />
              <DropdownMenuItem onClick={handleLogout} className="cursor-pointer text-rose-400 focus:bg-rose-500/10 focus:text-rose-300" data-testid="menu-logout">
                <LogOut className="w-4 h-4 mr-2" /> Sair
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </header>
        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

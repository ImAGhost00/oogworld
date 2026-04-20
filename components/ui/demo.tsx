import React from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuPage,
  DropdownMenuPageTrigger,
  DropdownMenuCheckboxItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
} from "@/components/ui/material-ui-dropdown-menu";
import {
  User,
  LogOut,
  Share2,
  Mail,
  MessageSquare,
  SlidersHorizontal,
  Moon,
  Sun,
  Bell,
  ShieldCheck,
} from "lucide-react";

export default function LayoutStressDemo() {
  return (
    <div className="relative w-full h-screen bg-muted/20 overflow-hidden font-sans">
      <div className="absolute top-6 left-6">
        <TriggerMenu label="Top Left" side="bottom" align="start" />
      </div>
      <div className="absolute top-6 right-6">
        <TriggerMenu label="Top Right" side="bottom" align="end" />
      </div>
      <div className="absolute bottom-6 left-6">
        <TriggerMenu label="Bottom Left" side="top" align="start" />
      </div>
      <div className="absolute bottom-6 right-6">
        <TriggerMenu label="Bottom Right" side="top" align="end" />
      </div>

      <div className="absolute top-6 left-1/2 -translate-x-1/2">
        <TriggerMenu label="Top Center" side="bottom" align="center" />
      </div>
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2">
        <TriggerMenu label="Bottom Center" side="top" align="center" />
      </div>

      <div className="absolute left-6 top-1/2 -translate-y-1/2">
        <TriggerMenu label="Left Side" side="right" align="center" />
      </div>
      <div className="absolute right-6 top-1/2 -translate-y-1/2">
        <TriggerMenu label="Right Side" side="left" align="center" />
      </div>

      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
        <TriggerMenu label="Center Pivot" side="bottom" align="center" />
      </div>
    </div>
  );
}

function TriggerMenu({
  label,
  side = "bottom",
  align = "center",
}: {
  label: string;
  side?: "top" | "bottom" | "left" | "right";
  align?: "start" | "center" | "end";
}) {
  const [theme, setTheme] = React.useState("dark");

  const [notifications, setNotifications] = React.useState(true);
  const [securityAlerts, setSecurityAlerts] = React.useState(false);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="px-5 py-2.5 bg-card border border-border/60 rounded-xl shadow-sm text-sm font-semibold hover:bg-muted transition-all active:scale-[0.98]">
        {label}
      </DropdownMenuTrigger>

      <DropdownMenuContent className="min-w-[16rem] w-auto" side={side} align={align}>
        <DropdownMenuPage id="main">
          <DropdownMenuLabel>Menu Actions</DropdownMenuLabel>

          <DropdownMenuItem>
            <User className="w-4 h-4 text-muted-foreground" />
            <span>Profile Settings</span>
          </DropdownMenuItem>

          <DropdownMenuSeparator />

          <DropdownMenuPageTrigger targetId="share">
            <Share2 className="w-4 h-4 text-muted-foreground" />
            <span>Share Project</span>
          </DropdownMenuPageTrigger>

          <DropdownMenuPageTrigger targetId="preferences">
            <SlidersHorizontal className="w-4 h-4 text-muted-foreground" />
            <span>Quick Preferences</span>
          </DropdownMenuPageTrigger>

          <DropdownMenuSeparator />

          <DropdownMenuItem className="text-destructive focus:bg-destructive/10">
            <LogOut className="w-4 h-4" />
            <span>Sign Out</span>
          </DropdownMenuItem>
        </DropdownMenuPage>

        <DropdownMenuPage id="share">
          <DropdownMenuItem>
            <Mail className="w-4 h-4 text-muted-foreground" />
            <span>Send Email</span>
          </DropdownMenuItem>

          <DropdownMenuItem>
            <MessageSquare className="w-4 h-4 text-muted-foreground" />
            <span>Copy Link</span>
          </DropdownMenuItem>
        </DropdownMenuPage>

        <DropdownMenuPage id="preferences">
          <DropdownMenuLabel>Theme Mode</DropdownMenuLabel>
          <DropdownMenuRadioGroup value={theme} onValueChange={setTheme}>
            <DropdownMenuRadioItem value="light">
              <Sun className="mr-2 w-4 h-4 opacity-50" />
              Light Mode
            </DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="dark">
              <Moon className="mr-2 w-4 h-4 opacity-50" />
              Dark Mode
            </DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>

          <DropdownMenuSeparator />

          <DropdownMenuLabel>Notifications</DropdownMenuLabel>
          <DropdownMenuCheckboxItem
            checked={notifications}
            onCheckedChange={setNotifications}
            onSelect={(e) => e.preventDefault()}
          >
            <Bell className="mr-2 w-4 h-4 opacity-50" />
            Enable Audio
          </DropdownMenuCheckboxItem>

          <DropdownMenuCheckboxItem
            checked={securityAlerts}
            onCheckedChange={setSecurityAlerts}
            onSelect={(e) => e.preventDefault()}
          >
            <ShieldCheck className="mr-2 w-4 h-4 opacity-50" />
            Security Alerts
          </DropdownMenuCheckboxItem>
        </DropdownMenuPage>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

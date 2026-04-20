import { Checkbox } from "@/components/ui/interfaces-checkbox";
import { Label } from "@/components/ui/label";

export default function CheckboxDemo() {
  return (
    <div className="flex flex-col items-center justify-center w-full min-h-screen bg-background p-8 overflow-hidden gap-8">
      <div className="flex items-baseline gap-0 text-3xl font-bold tracking-tight select-none">
        <span className="line-through text-muted-foreground opacity-60">ghost</span>
        <span className="text-primary">oog</span>
        <span className="text-foreground">world.dev</span>
      </div>

      <div className="flex items-center gap-2">
        <Checkbox id="terms" />
        <Label htmlFor="terms">Accept terms and conditions</Label>
      </div>
    </div>
  );
}

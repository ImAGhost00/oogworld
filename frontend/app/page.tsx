import { Checkbox } from "@/components/ui/interfaces-checkbox";
import { Label } from "@/components/ui/label";

export default function CheckboxDemo() {
  return (
    <div className="flex items-center justify-center w-full min-h-screen bg-background p-8 overflow-hidden">
      <div className="flex items-center gap-2">
        <Checkbox id="terms" />
        <Label htmlFor="terms">Accept terms and conditions</Label>
      </div>
    </div>
  );
}

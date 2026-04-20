import { Checkbox } from "@/components/ui/checkbox";
import { CheckboxGroup } from "@/components/ui/checkbox-group";
import { Label } from "@/components/ui/label";

export default function CheckboxGroupDefault() {
  return (
    <div className="flex items-center justify-center w-full min-h-screen bg-background">
      <CheckboxGroup aria-label="Select frameworks" defaultValue={["next"]}>
        <Label className="flex items-center gap-2">
          <Checkbox value="next" />
          Next.js
        </Label>
        <Label className="flex items-center gap-2">
          <Checkbox value="vite" />
          Vite
        </Label>
        <Label className="flex items-center gap-2">
          <Checkbox value="astro" />
          Astro
        </Label>
      </CheckboxGroup>
    </div>
  );
}

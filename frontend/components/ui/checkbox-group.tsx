"use client";

import { CheckboxGroup as CheckboxGroupPrimitive } from "@base-ui/react/checkbox-group";
import type React from "react";

function cn(...inputs: (string | undefined | null | false)[]) {
  return inputs.filter(Boolean).join(" ");
}

export function CheckboxGroup({
  className,
  ...props
}: CheckboxGroupPrimitive.Props): React.ReactElement {
  const rootClassName =
    typeof className === "function"
      ? (state: Parameters<NonNullable<typeof className>>[0]) =>
          cn("flex flex-col items-start gap-3", className(state))
      : cn("flex flex-col items-start gap-3", className);

  return (
    <CheckboxGroupPrimitive
      className={rootClassName}
      {...props}
    />
  );
}

export { CheckboxGroupPrimitive };

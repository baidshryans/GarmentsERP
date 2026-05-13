import * as React from "react"

import { cn } from "@/lib/utils"

const Input = React.forwardRef(({ className, type, ...props }, ref) => {
  return (
    (<input
      type={type}
      className={cn(
        // Layout & sizing
        "flex h-9 w-full px-3 py-2 text-sm",
        // Border & shape
        "rounded-lg border border-gray-200",
        // Background & shadow
        "bg-white shadow-sm",
        // Typography
        "text-foreground placeholder:text-gray-400",
        // Transitions
        "transition-all duration-200 ease-in-out",
        // Hover
        "hover:border-violet-400/70 hover:shadow-md",
        // Focus � violet glow ring
        "focus-visible:outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/20 focus-visible:shadow-md",
        // File input
        "file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground",
        // Disabled
        "disabled:cursor-not-allowed disabled:bg-gray-50 disabled:opacity-50 disabled:shadow-none",
        className
      )}
      min="0"
      ref={ref}
      {...props} />)
  );
})
Input.displayName = "Input"

export { Input }

import { cn } from "@/lib/utils";

const variantClasses = {
  default:     "bg-primary text-primary-foreground",
  secondary:   "bg-secondary text-secondary-foreground",
  destructive: "bg-destructive text-destructive-foreground",
  outline:     "border border-input text-foreground",
};

export function Badge({ className, variant = "default", children, ...props }) {
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-full font-semibold",
        variantClasses[variant] ?? variantClasses.default,
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}

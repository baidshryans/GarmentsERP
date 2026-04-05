import * as React from "react"
import { cn } from "@/lib/utils"

const RadioGroup = React.forwardRef(({ className, value, onValueChange, ...props }, ref) => {
    return (
        <div
            ref={ref}
            role="radiogroup"
            className={cn("grid gap-2", className)}
            {...props}
        >
            {React.Children.map(props.children, (child) => {
                if (React.isValidElement(child)) {
                    return React.cloneElement(child, {
                        checked: child.props.value === value,
                        onChange: () => onValueChange?.(child.props.value),
                    })
                }
                return child
            })}
        </div>
    )
})
RadioGroup.displayName = "RadioGroup"

const RadioGroupItem = React.forwardRef(({ className, value, checked, onChange, ...props }, ref) => {
    return (
        <input
            ref={ref}
            type="radio"
            value={value}
            checked={checked}
            onChange={onChange}
            className={cn(
                "aspect-square h-4 w-4 rounded-full border border-primary text-primary ring-offset-background focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
                className
            )}
            {...props}
        />
    )
})
RadioGroupItem.displayName = "RadioGroupItem"

export { RadioGroup, RadioGroupItem }
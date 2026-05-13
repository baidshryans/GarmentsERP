import { LoginForm } from "@/components/login-form"
import { Gem } from "lucide-react"

export default function Page() {
  return (
    <div className="flex h-screen w-full">
      {/* Left branding panel � Excalidraw-inspired */}
      <div className="hidden md:flex md:w-1/2 flex-col items-center justify-center bg-violet-50 p-12">
        <div className="flex flex-col items-center gap-6 max-w-xs text-center">
          <div className="flex items-center justify-center size-16 rounded-2xl bg-primary shadow-lg shadow-violet-200">
            <Gem className="size-8 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-wide text-gray-900">Jewel India</h1>
            <p className="text-primary text-sm font-medium mt-1 tracking-widest uppercase">ERP System</p>
          </div>
          <p className="text-gray-500 text-sm leading-relaxed">
            Complete jewellery business management � sales, inventory, manufacturing, and accounts in one place.
          </p>
        </div>
      </div>

      {/* Right login panel */}
      <div className="flex w-full md:w-1/2 items-center justify-center bg-background px-8">
        <LoginForm />
      </div>
    </div>
  );
}

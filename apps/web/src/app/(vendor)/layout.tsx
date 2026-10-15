import { VendorShell } from "@/components/vendor/vendor-shell";

export default function VendorLayout({ children }: { children: React.ReactNode }) {
  return <VendorShell>{children}</VendorShell>;
}

import Link from "next/link";
import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface NavLinkProps {
  href: string;
  className?: string;
  activeClassName?: string;
  children: ReactNode;
  [key: string]: any;
}

export function NavLink({ href, className, activeClassName, children, ...props }: NavLinkProps) {
  return (
    <Link href={href} className={cn(className)} {...props}>
      {children}
    </Link>
  );
}

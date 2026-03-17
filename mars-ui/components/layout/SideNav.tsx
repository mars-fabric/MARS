'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutGrid,
  ListTodo,
  History,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'

interface SideNavProps {
  collapsed: boolean
  onToggle: () => void
}

const navItems = [
  { id: 'modes', label: 'Modes', icon: LayoutGrid, href: '/' },
  { id: 'tasks', label: 'Tasks', icon: ListTodo, href: '/tasks' },
  { id: 'sessions', label: 'Sessions', icon: History, href: '/sessions' },
]

export default function SideNav({ collapsed, onToggle }: SideNavProps) {
  const pathname = usePathname()

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/'
    return pathname.startsWith(href)
  }

  return (
    <nav
      className="h-full flex flex-col border-r transition-all duration-mars-slow"
      style={{
        width: collapsed ? 'var(--mars-sidenav-collapsed-width)' : 'var(--mars-sidenav-width)',
        backgroundColor: 'var(--mars-color-surface-raised)',
        borderColor: 'var(--mars-color-border)',
      }}
      aria-label="Main navigation"
    >
      {/* Nav Items */}
      <div className="flex-1 py-2">
        {navItems.map((item) => {
          const Icon = item.icon
          const active = isActive(item.href)
          return (
            <Link
              key={item.id}
              href={item.href}
              prefetch={true}
              className={`
                w-full flex items-center gap-3 px-4 py-3 text-sm font-medium
                transition-colors duration-mars-fast
                ${active
                  ? 'text-[var(--mars-color-primary)] bg-[var(--mars-color-primary-subtle)]'
                  : 'text-[var(--mars-color-text-secondary)] hover:text-[var(--mars-color-text)] hover:bg-[var(--mars-color-bg-hover)]'
                }
              `}
              aria-current={active ? 'page' : undefined}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          )
        })}
      </div>

      {/* Collapse Toggle */}
      <div className="border-t py-2" style={{ borderColor: 'var(--mars-color-border)' }}>
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-center gap-3 px-4 py-2 text-sm
            text-[var(--mars-color-text-tertiary)] hover:text-[var(--mars-color-text)]
            transition-colors duration-mars-fast"
          aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <>
              <ChevronLeft className="w-4 h-4" />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </nav>
  )
}

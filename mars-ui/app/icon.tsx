export const size = { width: 32, height: 32 }
export const contentType = 'image/svg+xml'

export default function Icon() {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
    <rect width="32" height="32" rx="6" fill="#3B82F6"/>
    <text x="16" y="22" font-family="system-ui,sans-serif" font-size="18" font-weight="700" fill="white" text-anchor="middle">M</text>
  </svg>`
  return new Response(svg, {
    headers: { 'Content-Type': 'image/svg+xml' },
  })
}

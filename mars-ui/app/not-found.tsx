import Link from 'next/link'

export default function NotFound() {
  return (
    <div
      className="flex h-full items-center justify-center"
      style={{ backgroundColor: 'var(--mars-color-bg)' }}
    >
      <div className="text-center">
        <h1
          className="text-6xl font-bold mb-2"
          style={{ color: 'var(--mars-color-primary)' }}
        >
          404
        </h1>
        <p
          className="text-lg mb-6"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          Page not found
        </p>
        <Link
          href="/"
          className="inline-block px-4 py-2 rounded-mars-md text-sm font-medium transition-colors duration-mars-fast"
          style={{
            backgroundColor: 'var(--mars-color-primary)',
            color: 'white',
          }}
        >
          Back to MARS
        </Link>
      </div>
    </div>
  );
}

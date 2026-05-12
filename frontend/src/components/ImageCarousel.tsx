import { useState } from 'react'

interface ImageCarouselProps {
  images: string[]
  linkUrl: string
  className?: string
}

export function ImageCarousel({ images, linkUrl, className = '' }: ImageCarouselProps) {
  const [idx, setIdx] = useState(0)

  if (images.length === 0) {
    return (
      <div className={`bg-gray-700 rounded flex items-center justify-center text-gray-500 text-xs ${className}`}>
        No photos
      </div>
    )
  }

  const prev = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIdx(i => (i - 1 + images.length) % images.length)
  }

  const next = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIdx(i => (i + 1) % images.length)
  }

  return (
    <div className={`relative group shrink-0 ${className}`}>
      <a href={linkUrl} target="_blank" rel="noopener noreferrer">
        <img
          src={images[idx]}
          alt=""
          className="w-full h-full object-cover rounded"
          onError={e => {
            const el = e.target as HTMLImageElement
            // Skip broken images
            const next = (idx + 1) % images.length
            if (next !== idx) setIdx(next)
            else el.style.display = 'none'
          }}
        />
      </a>

      {/* Counter */}
      {images.length > 1 && (
        <span className="absolute bottom-1 right-1 bg-black/60 text-white text-xs px-1.5 py-0.5 rounded">
          {idx + 1}/{images.length}
        </span>
      )}

      {/* Arrows — only show when multiple images */}
      {images.length > 1 && (
        <>
          <button
            onClick={prev}
            className="absolute left-0 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/80 text-white px-1.5 py-2 rounded-r opacity-0 group-hover:opacity-100 transition-opacity text-xs"
          >
            ‹
          </button>
          <button
            onClick={next}
            className="absolute right-0 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/80 text-white px-1.5 py-2 rounded-l opacity-0 group-hover:opacity-100 transition-opacity text-xs"
          >
            ›
          </button>
        </>
      )}
    </div>
  )
}

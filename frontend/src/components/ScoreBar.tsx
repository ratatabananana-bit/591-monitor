export function ScoreBar({ score }: { score: number | null }) {
  if (score === null) return <span className="text-gray-500">—</span>
  const color = score >= 70 ? 'bg-green-500' : score >= 40 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-2 bg-gray-700 rounded overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-sm">{score.toFixed(0)}</span>
    </div>
  )
}

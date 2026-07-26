export function SkeletonLine({ width = "100%", height = "16px", className = "" }) {
    return (
        <div
            className={`bg-surfaceLight rounded-lg animate-pulse ${className}`}
            style={{ width, height }}
        />
    )
}

export function SkeletonCard({ className = "" }) {
    return (
        <div className={`card p-5 space-y-3 ${className}`}>
            <SkeletonLine width="60%" height="18px" />
            <SkeletonLine width="100%" />
            <SkeletonLine width="80%" />
        </div>
    )
}

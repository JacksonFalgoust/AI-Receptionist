import { useQuery } from '@tanstack/react-query'

import { PageHeader } from '@/components/ui/PageHeader'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { FEATURES_KEY, FeatureCard } from '@/features/features/FeatureCard'
import { featureService } from '@/services/featureService'

/**
 * US-7.1. Owns the list query; each `FeatureCard` owns its own toggle
 * mutation and patches this same query's cache on success.
 */
export function FeaturesPage() {
  const query = useQuery({
    queryKey: FEATURES_KEY,
    queryFn: () => featureService.list(),
  })

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Features"
        description="Enable or disable what Concierge is allowed to do for your customers."
      />
      <QueryBoundary
        query={query}
        skeletonRows={6}
        isEmpty={(features) => features.length === 0}
        empty={{ title: 'No features available' }}
      >
        {(features) => (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
              <FeatureCard key={feature.id} feature={feature} />
            ))}
          </div>
        )}
      </QueryBoundary>
    </div>
  )
}

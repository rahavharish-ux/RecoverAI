export interface PolicyConfig {
  policy_version: string
  max_retry_attempts: number
  retry_cooldown_hours: number
  automated_actions_enabled: boolean
  action_costs_cents: Record<string, number>
  note: string
}

export async function getPolicyConfig(): Promise<PolicyConfig> {
  const response = await fetch('/api/v1/policy')
  if (!response.ok) throw new Error(`GET /api/v1/policy failed: ${response.status}`)
  return (await response.json()) as PolicyConfig
}

export function trackEvent(event: string, data?: Record<string, any>) {
  if (typeof window !== 'undefined' && (window as any).__MARS_TELEMETRY__) {
    (window as any).__MARS_TELEMETRY__.track(event, data)
  }
  if (process.env.NEXT_PUBLIC_DEBUG === 'true') {
    console.log(`[MARS Telemetry] ${event}`, data)
  }
}

export const EVENTS = {
  MODAL_OPENED: 'modal_opened',
  MODAL_CLOSED: 'modal_closed',
  SESSION_LAUNCHED: 'session_launched',
  SESSION_SWITCHED: 'session_switched',
  SESSION_PAUSED: 'session_paused',
  SESSION_RESUMED: 'session_resumed',
  MODE_SELECTED: 'mode_selected',
  TASK_OPENED: 'task_opened',
  THEME_TOGGLED: 'theme_toggled',
}

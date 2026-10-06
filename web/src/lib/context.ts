import { createContext, useContext } from 'react'
import type { AppState } from './store'

export const AppContext = createContext<AppState | null>(null)
export function useApp() { const state = useContext(AppContext); if (!state) throw new Error('AppProvider is required'); return state }

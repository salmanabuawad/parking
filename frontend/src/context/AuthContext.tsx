import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import api from '../api'

interface User {
  username: string
}

interface AuthContextValue {
  token: string | null
  user: User | null
  login: (username: string, password: string) => Promise<{ access_token: string; username: string }>
  logout: () => void
  isLoggedIn: boolean
  loading: boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

const TOKEN_KEY = 'parking_token'
const USER_KEY = 'parking_user'

function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.exp && payload.exp * 1000 < Date.now()
  } catch {
    return true // malformed token — treat as expired
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => {
    const t = localStorage.getItem(TOKEN_KEY)
    if (t && isTokenExpired(t)) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      return null
    }
    return t
  })
  const [user, setUser] = useState<User | null>(() => {
    try {
      const u = localStorage.getItem(USER_KEY)
      return u ? JSON.parse(u) : null
    } catch {
      return null
    }
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY)
    if (stored && isTokenExpired(stored)) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      setToken(null)
      setUser(null)
    } else {
      setToken(stored)
      try {
        const u = localStorage.getItem(USER_KEY)
        setUser(u ? JSON.parse(u) : null)
      } catch {
        setUser(null)
      }
    }
    setLoading(false)
  }, [])

  const login = async (username: string, password: string) => {
    const { data } = await api.post<{ access_token: string; username: string }>('/login', {
      username,
      password,
    })
    const t = data.access_token
    const u = { username: data.username }
    localStorage.setItem(TOKEN_KEY, t)
    localStorage.setItem(USER_KEY, JSON.stringify(u))
    setToken(t)
    setUser(u)
    return data
  }

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUser(null)
  }

  const value: AuthContextValue = { token, user, login, logout, isLoggedIn: !!token, loading }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

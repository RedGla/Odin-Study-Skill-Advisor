import { useEffect, useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { apiClient } from '../api/client';

export default function ProtectedRoute() {
  const [status, setStatus] = useState<'loading' | 'authed' | 'unauthed'>('loading');
  const [role, setRole] = useState<string | null>(null);
  const location = useLocation();

  useEffect(() => {
    apiClient.get('/auth/me')
      .then(({ data }) => {
        setRole(data.role);
        setStatus('authed');
      })
      .catch(() => setStatus('unauthed'));
  }, []);

  if (status === 'loading') return <div className="flex h-screen items-center justify-center">Loading…</div>;
  if (status === 'unauthed') return <Navigate to="/login" replace />;
  if (location.pathname.startsWith('/admin') && role !== 'admin') {
    return <Navigate to="/" replace />;
  }
  if (role === 'admin' && location.pathname === '/') {
    return <Navigate to="/admin" replace />;
  }
  return <Outlet />;
}
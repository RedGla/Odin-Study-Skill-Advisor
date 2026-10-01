import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useEffect } from 'react';
import Login from './pages/Login';
import Admin from './pages/Admin';
import AppShell from './components/AppShell';
import ProtectedRoute from './components/ProtectedRoute';
import Settings from './pages/Settings';

export default function App() {
  useEffect(() => {
    document.documentElement.dataset.theme = localStorage.getItem('odin-theme') === 'dark' ? 'dark' : 'light';
  }, []);
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/admin" element={<Admin />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/" element={<AppShell />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

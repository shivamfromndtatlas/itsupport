import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  TextField,
  Button,
  Typography,
  Alert,
  InputAdornment,
  IconButton,
  CircularProgress,
  Divider,
} from '@mui/material';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import DevicesOtherIcon from '@mui/icons-material/DevicesOther';
import InventoryIcon from '@mui/icons-material/Inventory';
import SupportAgentIcon from '@mui/icons-material/SupportAgent';
import { useAuth } from '../../context/AuthContext';

const FEATURES = [
  { icon: <DevicesOtherIcon sx={{ fontSize: 18 }} />, text: 'Asset & device management' },
  { icon: <InventoryIcon sx={{ fontSize: 18 }} />, text: 'Inventory tracking & allocation' },
  { icon: <SupportAgentIcon sx={{ fontSize: 18 }} />, text: 'IT ticket & SOP management' },
];

function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [form, setForm] = useState({ email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.email || !form.password) {
      setError('Please enter your email and password.');
      return;
    }
    setLoading(true);
    try {
      await login(form.email, form.password);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.response?.data?.non_field_errors?.[0] ||
        'Invalid email or password. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: '#F1F5F9' }}>
      {/* Left panel */}
      <Box
        sx={{
          display: { xs: 'none', md: 'flex' },
          flexDirection: 'column',
          justifyContent: 'center',
          width: '45%',
          minHeight: '100vh',
          background: 'linear-gradient(145deg, #0F172A 0%, #1E1B4B 50%, #312E81 100%)',
          p: 6,
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Background decorative circles */}
        <Box sx={{
          position: 'absolute', top: -80, right: -80,
          width: 320, height: 320, borderRadius: '50%',
          background: 'rgba(99,102,241,0.12)',
        }} />
        <Box sx={{
          position: 'absolute', bottom: -60, left: -60,
          width: 240, height: 240, borderRadius: '50%',
          background: 'rgba(124,58,237,0.1)',
        }} />

        {/* Logo */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 8 }}>
          <Box sx={{
            width: 42, height: 42, borderRadius: '12px',
            background: 'linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 8px 20px rgba(79,70,229,0.4)',
          }}>
            <Typography sx={{ color: '#fff', fontWeight: 800, fontSize: 17, letterSpacing: '-0.5px' }}>
              IT
            </Typography>
          </Box>
          <Box>
            <Typography sx={{ color: '#F8FAFC', fontWeight: 700, fontSize: 16, lineHeight: 1.2 }}>
              IT Support Portal
            </Typography>
            <Typography sx={{ color: '#94A3B8', fontSize: 12 }}>
              Enterprise Management
            </Typography>
          </Box>
        </Box>

        {/* Headline */}
        <Typography
          sx={{
            color: '#F8FAFC',
            fontWeight: 800,
            fontSize: { md: 30, lg: 36 },
            lineHeight: 1.2,
            mb: 2,
          }}
        >
          Manage your IT{' '}
          <Box component="span" sx={{ color: '#818CF8' }}>
            infrastructure
          </Box>{' '}
          with ease
        </Typography>
        <Typography sx={{ color: '#94A3B8', fontSize: 15, mb: 5, lineHeight: 1.7 }}>
          A unified platform for IT operations, asset management, and employee support.
        </Typography>

        {/* Feature list */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {FEATURES.map((f, i) => (
            <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Box sx={{
                width: 36, height: 36, borderRadius: '10px',
                background: 'rgba(99,102,241,0.15)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#818CF8', flexShrink: 0,
              }}>
                {f.icon}
              </Box>
              <Typography sx={{ color: '#CBD5E1', fontSize: 14 }}>{f.text}</Typography>
            </Box>
          ))}
        </Box>
      </Box>

      {/* Right panel */}
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          p: { xs: 2, sm: 4 },
        }}
      >
        <Box sx={{ width: '100%', maxWidth: 400 }}>
          {/* Mobile logo */}
          <Box sx={{ display: { xs: 'flex', md: 'none' }, alignItems: 'center', gap: 1.5, mb: 5, justifyContent: 'center' }}>
            <Box sx={{
              width: 40, height: 40, borderRadius: '10px',
              background: 'linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Typography sx={{ color: '#fff', fontWeight: 800, fontSize: 16 }}>IT</Typography>
            </Box>
            <Typography sx={{ fontWeight: 700, fontSize: 18, color: 'text.primary' }}>
              IT Support Portal
            </Typography>
          </Box>

          <Box sx={{ mb: 4 }}>
            <Box
              sx={{
                width: 48, height: 48, borderRadius: '14px',
                bgcolor: 'primary.light', display: 'flex',
                alignItems: 'center', justifyContent: 'center',
                mb: 2.5, color: 'primary.main',
                background: 'linear-gradient(135deg, rgba(79,70,229,0.1) 0%, rgba(124,58,237,0.15) 100%)',
              }}
            >
              <LockOutlinedIcon sx={{ fontSize: 22, color: 'primary.main' }} />
            </Box>
            <Typography variant="h5" fontWeight={800} color="text.primary" gutterBottom>
              Welcome back
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Sign in to your account to continue
            </Typography>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 2.5 }} onClose={() => setError('')}>
              {error}
            </Alert>
          )}

          <Box component="form" onSubmit={handleSubmit} noValidate>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" fontWeight={600} color="text.primary" sx={{ mb: 0.75 }}>
                Email address
              </Typography>
              <TextField
                name="email"
                type="email"
                fullWidth
                placeholder="you@company.com"
                value={form.email}
                onChange={handleChange}
                autoComplete="email"
                autoFocus
                required
                sx={{
                  '& .MuiOutlinedInput-root': {
                    height: 44,
                    fontSize: 14,
                  },
                }}
              />
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography variant="body2" fontWeight={600} color="text.primary" sx={{ mb: 0.75 }}>
                Password
              </Typography>
              <TextField
                name="password"
                type={showPassword ? 'text' : 'password'}
                fullWidth
                placeholder="Enter your password"
                value={form.password}
                onChange={handleChange}
                autoComplete="current-password"
                required
                sx={{
                  '& .MuiOutlinedInput-root': {
                    height: 44,
                    fontSize: 14,
                  },
                }}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        onClick={() => setShowPassword(!showPassword)}
                        edge="end"
                        size="small"
                        sx={{ color: 'text.secondary' }}
                      >
                        {showPassword ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
            </Box>

            <Button
              type="submit"
              fullWidth
              variant="contained"
              size="large"
              disabled={loading}
              sx={{
                height: 46,
                fontWeight: 700,
                fontSize: 15,
                background: 'linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%)',
                boxShadow: '0 4px 15px rgba(79,70,229,0.35)',
                '&:hover': {
                  background: 'linear-gradient(135deg, #4338CA 0%, #6D28D9 100%)',
                  boxShadow: '0 6px 20px rgba(79,70,229,0.45)',
                },
              }}
            >
              {loading ? <CircularProgress size={22} color="inherit" /> : 'Sign In'}
            </Button>
          </Box>

          <Divider sx={{ my: 3, borderColor: 'divider' }} />
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center' }}>
            Contact your IT administrator if you need access.
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}

export default Login;

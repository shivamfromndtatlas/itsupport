import React from 'react';
import { Box, Typography, Button } from '@mui/material';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

function ForbiddenPage() {
  const navigate = useNavigate();
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '60vh',
        gap: 2,
      }}
    >
      <LockOutlinedIcon sx={{ fontSize: 80, color: 'error.main' }} />
      <Typography variant="h4" fontWeight={700}>
        403 – Forbidden
      </Typography>
      <Typography variant="body1" color="text.secondary">
        You do not have permission to access this page.
      </Typography>
      <Button variant="contained" onClick={() => navigate('/dashboard')}>
        Go to Dashboard
      </Button>
    </Box>
  );
}

function RoleRoute({ children, roles }) {
  const { hasRole } = useAuth();

  if (!hasRole(...roles)) {
    return <ForbiddenPage />;
  }

  return children;
}

export default RoleRoute;

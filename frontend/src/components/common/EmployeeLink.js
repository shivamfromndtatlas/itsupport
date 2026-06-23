import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Link as MuiLink } from '@mui/material';

function EmployeeLink({ employeeId, children, sx, ...props }) {
  if (!employeeId) {
    return <>{children}</>;
  }

  return (
    <MuiLink
      component={RouterLink}
      to={`/employees/${employeeId}`}
      underline="hover"
      sx={{ fontWeight: 600, ...sx }}
      {...props}
    >
      {children}
    </MuiLink>
  );
}

export default EmployeeLink;

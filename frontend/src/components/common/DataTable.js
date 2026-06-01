import React, { useState, useMemo } from 'react';
import { DataGrid } from '@mui/x-data-grid';
import {
  Box,
  Button,
  TextField,
  Typography,
  InputAdornment,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import SearchIcon from '@mui/icons-material/Search';

function DataTable({
  rows = [],
  columns = [],
  loading = false,
  onAdd,
  addLabel = 'Add',
  title,
  searchable = false,
  toolbar,
  pageSize = 10,
  ...rest
}) {
  const [searchText, setSearchText] = useState('');

  const filteredRows = useMemo(() => {
    if (!searchable || !searchText.trim()) return rows;
    const lower = searchText.toLowerCase();
    return rows.filter((row) =>
      Object.values(row).some((val) =>
        String(val ?? '').toLowerCase().includes(lower)
      )
    );
  }, [rows, searchText, searchable]);

  return (
    <Box>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 2,
          flexWrap: 'wrap',
          gap: 1,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          {title && (
            <Typography variant="h6" fontWeight={600}>
              {title}
            </Typography>
          )}
          {toolbar}
          {searchable && (
            <TextField
              size="small"
              placeholder="Search..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
              sx={{ minWidth: 220 }}
            />
          )}
        </Box>
        {onAdd && (
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={onAdd}
            size="small"
          >
            {addLabel}
          </Button>
        )}
      </Box>

      {/* Grid */}
      <Box sx={{ width: '100%' }}>
        <DataGrid
          rows={filteredRows}
          columns={columns}
          loading={loading}
          initialState={{
            pagination: { paginationModel: { pageSize } },
          }}
          pageSizeOptions={[5, 10, 25, 50]}
          disableRowSelectionOnClick
          autoHeight
          sx={{
            border: 'none',
            '& .MuiDataGrid-columnHeaders': {
              backgroundColor: 'grey.100',
              fontWeight: 700,
            },
            '& .MuiDataGrid-row:hover': {
              backgroundColor: 'action.hover',
            },
            '& .MuiDataGrid-cell': {
              borderBottom: '1px solid',
              borderColor: 'divider',
            },
          }}
          {...rest}
        />
      </Box>
    </Box>
  );
}

export default DataTable;

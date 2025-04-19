// /frontend/src/DataForm.js

import { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Paper,
  Typography
} from '@mui/material';
import axios from 'axios';

const endpointMapping = {
  'Notion': 'notion',
  'Airtable': 'airtable',
  'HubSpot': 'hubspot'
};

export const DataForm = ({ integrationType, credentials }) => {
  const [loadedData, setLoadedData] = useState(null);
  const endpoint = endpointMapping[integrationType];

  const handleLoad = async () => {
    try {
      const formData = new FormData();
      formData.append('credentials', JSON.stringify(credentials));
      const { data } = await axios.post(
        `http://localhost:8000/integrations/${endpoint}/load`,
        formData
      );
      setLoadedData(data);
      console.log("Loaded Data:", data)
    } catch (e) {
      alert(e?.response?.data?.detail || e.message);
    }
  };

  const clear = () => setLoadedData(null);

  // Helper: render array of objects as a table
  const renderTable = (arr) => {
    if (arr.length === 0) {
      return <Typography>No items returned.</Typography>;
    }
    const columns = Object.keys(arr[0]);
    return (
      <Paper sx={{ width: '100%', overflowX: 'auto', mt: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              {columns.map((col) => (
                <TableCell key={col}><strong>{col}</strong></TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {arr.map((row, r) => (
              <TableRow key={r}>
                {columns.map((col) => {
                  let val = row[col];
                  if (typeof val === 'object' && val !== null) {
                    val = JSON.stringify(val);
                  }
                  return <TableCell key={col}>{val?.toString() ?? ''}</TableCell>;
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
    );
  };

  return (
    <Box
      display="flex"
      flexDirection="column"
      alignItems="center"
      width="100%"
      sx={{ mt: 2 }}
    >
      <Box width="100%" maxWidth={600}>
        <Button variant="contained" onClick={handleLoad}>
          Load Data
        </Button>
        <Button variant="outlined" onClick={clear} sx={{ ml: 2 }}>
          Clear
        </Button>

        {!loadedData && (
          <Typography sx={{ mt: 2 }} color="textSecondary">
            No data loaded yet.
          </Typography>
        )}

        {loadedData && Array.isArray(loadedData)
          ? renderTable(loadedData)
          : loadedData && (
            <TextField
              label="Loaded Data"
              value={JSON.stringify(loadedData, null, 2)}
              fullWidth
              multiline
              minRows={6}
              sx={{ mt: 2 }}
              InputLabelProps={{ shrink: true }}
            />
          )
        }
      </Box>
    </Box>
  );
};

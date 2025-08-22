import pkg from 'pg';
import dotenv from 'dotenv';

// Initialize dotenv to load environment variables
dotenv.config();

const { Pool } = pkg;

// Create a new pool instance using the connection string
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: {
    rejectUnauthorized: false
  }
});

// Test the connection
pool.connect()
  .then(() => {
    console.log('PostgreSQL database connected successfully');
  })
  .catch((error) => {
    console.error('PostgreSQL connection error:', error);
  });

// Export the pool to be used in other files
export default pool;
# Frontend Dockerfile for React/Vite
# Using Node.js 22 for Vite 7 compatibility
FROM node:22-alpine

WORKDIR /app

# Install dependencies first for better caching
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Expose port
EXPOSE 3000

# Start development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]

# Testing Rules

## Test Pyramid
- **Unit Tests**: 70% - Individual functions/methods
- **Integration Tests**: 20% - Component interaction
- **E2E Tests**: 10% - Overall system workflows

## Test Structure
- **AAA Pattern**: Arrange, Act, Assert
- Descriptive test names
- One assertion focus per test
- Independent tests (no mutual dependencies)

## Coverage
- Minimum: 80% code coverage
- Critical paths: 100%
- Cover edge cases
- Test error handling

## Best Practices
- Write tests before bug fixes (TDD)
- Mock external dependencies
- Use fixtures for test data
- Fast execution (< 10 seconds)
- Deterministic tests (no flakiness)

## Test Data
- Use realistic data
- Prefer anonymized production data
- Version test data in repository
- Cleanup after tests


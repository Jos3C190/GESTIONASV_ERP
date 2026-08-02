"""Employee/Department use cases barrel."""
from app.application.employees.department_crud import (
    CreateDepartmentInput,
    CreateDepartmentUseCase,
    DeleteDepartmentUseCase,
    GetDepartmentUseCase,
    ListDepartmentsUseCase,
    UpdateDepartmentInput,
    UpdateDepartmentUseCase,
)
from app.application.employees.employee_crud import (
    CreateEmployeeInput,
    CreateEmployeeUseCase,
    DeleteEmployeeUseCase,
    GetEmployeeUseCase,
    LinkUserInput,
    LinkUserUseCase,
    ListEmployeesInput,
    ListEmployeesResult,
    ListEmployeesUseCase,
    UpdateEmployeeInput,
    UpdateEmployeeUseCase,
)

__all__ = [
    "CreateDepartmentInput",
    "CreateDepartmentUseCase",
    "CreateEmployeeInput",
    "CreateEmployeeUseCase",
    "DeleteDepartmentUseCase",
    "DeleteEmployeeUseCase",
    "GetDepartmentUseCase",
    "GetEmployeeUseCase",
    "LinkUserInput",
    "LinkUserUseCase",
    "ListDepartmentsUseCase",
    "ListEmployeesInput",
    "ListEmployeesResult",
    "ListEmployeesUseCase",
    "UpdateDepartmentInput",
    "UpdateDepartmentUseCase",
    "UpdateEmployeeInput",
    "UpdateEmployeeUseCase",
]

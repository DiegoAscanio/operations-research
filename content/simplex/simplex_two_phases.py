from typing import Any
import numpy as np
from copy import deepcopy
import pdb

def _compute_x_from_x_I(n, I, x_I):
    x = np.zeros(n)
    x[I] = x_I
    return x

def _compute_A_I(A: np.ndarray, I: list) -> np.ndarray:
    A_I = A[:, I]
    return A_I

def _compute_J(n: int, I: list) -> list:
    J = np.setdiff1d(np.arange(n), I)
    return list(J)

def _compute_A_J(A: np.ndarray, J: list) -> np.ndarray:
    A_J = A[:, J]
    return A_J

def _compute_X_I(A_I: np.ndarray, b: np.ndarray) -> np.ndarray:
    X_I = np.linalg.inv(A_I).dot(b)
    return X_I

def _compute_A_I_x_I_π_and_z_0(A: np.ndarray, b: np.ndarray, c: np.ndarray, I: list) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    # A_I should be a submatrix from A with columns indexed (and sorted) by I
    A_I = _compute_A_I(A, I)
    A_I_inv = np.linalg.inv(A_I)
    # C_I should be a submatrix from c with columns indexed (and sorted) by I
    c_I = c[I]

    x_I = _compute_X_I(A_I, b)
    π = c_I.dot(A_I_inv)
    z_0 = π.dot(b)
    return A_I, x_I, π, z_0

def _compute_c_hat_J(π: np.ndarray, A: np.ndarray, c: np.ndarray, J: list) -> np.ndarray:
    A_J = A[:, J]
    c_hat_J = π.dot(A_J) - c[J]
    return c_hat_J

def _find_k_who_enters(c_hat_J: np.ndarray) -> tuple[np.intp, bool]:
    """
    Finds the index of the variable that enters the basis and returns if
    the simplex method shouuld continue. When c_hat_J[k] <= 0, the method
    found an optimal, unique and finite solution and, therefore, should stop.
    Args:
        c_hat_J: the vector of the reduced costs of the non-basic variables.
    Returns:
        k: the index of the variable that enters the basis.
        proceed_: a boolean indicating if the simplex method should proceed.
    """
    k: np.intp = np.argmax(c_hat_J)
    return k, c_hat_J[k] > 0

def _find_r_who_leaves_cycle_allowed(I: list, A_I_inv: np.ndarray, x_I: np.ndarray, A_k: np.ndarray, debug = False) -> tuple[np.intp, np.ndarray, bool, dict]:
    """
    Finds the index of the variable that leaves the basis and returns if
    the simplex method shouuld continue. When all elements of A_k are
    non-positive, the method found an unbounded solution and, therefore,
    should stop. NOT CYCLE-PROOF.
    Args:
        I: list of basic variables
        A_I_inv: the inverse of the matrix of the basic variables.
        x_I: the vector of the basic variables.
        A_k: the vector of the coefficients of the entering variable.
        debug: a boolean variable to print the steps of the simplex method.
    Returns:
        r: the index of the variable that leaves the basis.
        y_k: the vector of the coefficients of the entering variable.
        proceed_: a boolean indicating if the simplex method should proceed.
                  if y_k[r] <= 0, the solution is unbounded and, therefre,
                  the method should stop.
        debug_info: a dictionary with debug information.
    """
    debug_info = {}

    # 1. compute y_k
    y_k = A_I_inv.dot(A_k)

    ratios = np.where(y_k > 0, x_I / y_k, np.inf)

    # 2. Variable index to leave the basis
    r = np.argmin(ratios)

    # 3. Append debug information
    if debug:
        debug_info['description'] = 'Finding the variable that leaves the basis'
        debug_info['y_k'] = y_k
        debug_info['ratios'] = ratios
        debug_info['r'] = r
        debug_info['I_r'] = I[r]

    # 6. Return the variable index to leave the basis and if the simplex method should proceed
    return r, y_k, np.any(y_k > 0), debug_info

def _find_r_who_leaves_cycle_proof(
    I : list,
    A : np.ndarray,
    A_I_inv : np.ndarray,
    B_prime : np.ndarray,
    y_k : np.ndarray,
    k : np.intp,
    debug = False
) -> tuple[np.intp, np.ndarray, bool, dict]:
    """
    Finds the index of the variable that leaves the basis and returns if
    the simplex method shouuld continue. When all elements of A_k are
    non-positive, the method found an unbounded solution and, therefore,
    should stop. CYCLE-PROOF.
    Args:
        I: list of basic variables
        A: the matrix of coefficients of the constraints.
        A_I_inv: the inverse of the matrix of the basic variables.
        B_prime: the vector of the right-hand side of the constraints.
        y_k: the vector of the coefficients of the entering variable.
        k: the index of the variable that enters the basis.
    Returns:
        r: the index of the variable that leaves the basis.
        y_k: the vector of the coefficients of the entering variable.
        proceed_: a boolean indicating if the simplex method should proceed.
                  if y_k[r] <= 0, the solution is unbounded and, therefre,
                  the method should stop.
        debug_info: a dictionary with debug information.
    """
    debug_info = {}
    _, n = A.shape
    columns = iter(set(range(n)) - set([k]))
    ratios = np.where(y_k > 0, B_prime / y_k, np.inf)
    aux_ratios = np.copy(ratios)

    # start lexicographic rule
    minimum_value = np.min(ratios)
    minimum_values_indices, *_ = np.where(ratios == minimum_value)
    candidate_indices_to_leave = np.copy(minimum_values_indices)

    # as in revised tableau we try to compute r to leave anyway
    # even after an optimal was reached, when this happens, all
    # y_k become leq 0, so ratios we'll become an array of inf
    # then, candidate_indices we'll have a length of I, as all
    # ratios are infinity. So that's why we added this or
    # to the implementation. Not the most elegant solution.
    # this one would be to refactor main step into a pipeline
    # where find_r_to_leave would be decorated through a pipeline
    # function who would receive proceed from _find_k_to_enter as 
    # a parameter and only runs if proceed is True.
    # but as we're losing a lot of time trying to prevent cycles
    # and fixing the bugs that naturally happens when doing so,
    # we'll leave this solution as it is. We should prefer simplicity
    # over complexity and this is simple enough to guarantee the proper
    # execution of our code.
    singleton = len(candidate_indices_to_leave) == 1 or minimum_value == np.inf
    # we can set r to the argmin of ratios as
    # if it is a singleton, it will be the only minimum in the array
    # but if it is not, r will be updated inside the loop until we find
    # a singleton set
    r = np.argmin(ratios)
    while not singleton:
        c = next(columns)
        y_c = A_I_inv @ A[:, c]
        aux_ratios = np.where(y_k > 0, y_c / y_k, np.inf)
        minimum_value = np.min(aux_ratios)
        minimum_values_indices, *_ = np.where(aux_ratios == minimum_value)
        singleton = len(minimum_values_indices) == 1
        r = np.argmin(aux_ratios)
        # As our A_I matrix is non-singular, we are guaranteed to find a singleton
        # so, the last computed r is guaranteed to come from a singleton set
        # as the last computed aux_ratios will produce a singleton min
        # safely retrieve it as a variable to leave the basis
    # Append debug information
    if debug:
        debug_info['description'] = 'Finding the variable that leaves the basis'
        debug_info['y_k'] = y_k
        debug_info['ratios'] = ratios
        debug_info['r'] = r
        debug_info['I_r'] = I[r]
    # Return the variable index to leave the basis and if the simplex
    # method should proceed
    return r, y_k, np.any(y_k > 0), debug_info

def _find_r_who_leaves(
    I: list,
    A_I_inv: np.ndarray,
    x_I: np.ndarray,
    A_k: np.ndarray,
    A : np.ndarray,
    k: np.intp,
    debug = False,
    cycle_proof = True
) -> tuple[np.intp, np.ndarray, bool, dict]:
    """
    Finds the index of the variable that leaves the basis and returns if
    the simplex method shouuld continue. When all elements of A_k are
    non-positive, the method found an unbounded solution and, therefore,
    should stop.
    Args:
        I: list of basic variables
        A_I_inv: the inverse of the matrix of the basic variables.
        x_I: the vector of the basic variables.
        A_k: the vector of the coefficients of the entering variable.
        A: the matrix of coefficients of the constraints.
        k: the index of the variable that enters the basis.
        debug: a boolean variable to print the steps of the simplex method.
        cycle_proof: a boolean variable to indicate if the method should 
        be cycle-proof or not.
    Returns:
        r: the index of the variable that leaves the basis.
        y_k: the vector of the coefficients of the entering variable.
        proceed_: a boolean indicating if the simplex method should proceed.
                  if y_k[r] <= 0, the solution is unbounded and, therefre,
                  the method should stop.
        debug_info: a dictionary with debug information.
    """
    return _find_r_who_leaves_cycle_proof(
        I = I,
        A = A,
        A_I_inv = A_I_inv,
        B_prime = x_I,
        y_k = A_I_inv @ A_k,
        k = k,
        debug = debug
    ) if cycle_proof else _find_r_who_leaves_cycle_allowed(
        I = I,
        A_I_inv = A_I_inv,
        x_I = x_I,
        A_k = A_k,
        debug = debug
    )

def _update_I_and_J(I: list, J: list, k: np.intp, r: np.intp) -> tuple[list, list]:
    """
    Updates the sets of basic and non-basic variables.
    Args:
        I: the set of indices of the basic variables.
        J: the set of indices of the non-basic variables.
        k: the index of the variable that enters the basis.
        r: the index of the variable that leaves the basis.
    Returns:
        I: the updated set of indices of the basic variables.
        J: the updated set of indices of the non-basic variables.
    """
    I = deepcopy(I)
    J = deepcopy(J)
    to_enter = deepcopy(J[k])
    to_exit = deepcopy(I[r])
    I[r] = to_enter
    J[k] = to_exit
    return I, J

def _drive_artificial_variables_out_of_basis(
    A_artificial: np.ndarray,
    A_original: np.ndarray,
    b: np.ndarray,
    c_artificial: np.ndarray,
    I_from_phase_1: list,
    artificial_variables: list
):
    _, n = A_original.shape
    # this J set contains all non basic variables
    # from the original problem that might be used
    # to replace the artificial variables in the basis
    # but not all of them are suitable for this task
    # only those who have a positive reduced cost, whose
    # c_hat_j >= 0
    J = list(set(range(n)) - set(I_from_phase_1))
    # 1. compute pi
    A_I_inv = np.linalg.inv(_compute_A_I(A_artificial, I_from_phase_1))
    π = c_artificial[I_from_phase_1] @ A_I_inv
    # 2. compute c_hat_J
    c_hat_J = π @ A_artificial[:, J] - c_artificial[J]
    # 3. build a list of valid non-basic variables to enter the basis
    J_valid_filter, *_ = np.where(c_hat_J >= 0)
    J_valid = [J[j] for j in J_valid_filter]
    # Now we'll build an strategy to drive artificial variables out of the basis
    # We can build a map relating the artificial variable and it's valid non-basic
    # replacement, if possible. It it is not possible, we'll map it to None and
    # then as the last step we'll rearange our basis to let the artificial variables
    # that cannot be replaced by non-basic variables to be the last ones in the basis
    # then we'll replace all replaceable artificial variables by non-basic variables
    # and drop the not replaceable from the basis, as well as the constraints that
    # contain them, as they're redundant and not necessary anymore.
    replacement_map = {}
    for r_artificial in artificial_variables:
        replacement_map[r_artificial] = None
        for k_valid_candidate in J_valid:
            r = I_from_phase_1.index(r_artificial)
            k = J.index(k_valid_candidate)
            aux_I = I_from_phase_1.copy()
            aux_J = J.copy()
            aux_I, aux_J = _update_I_and_J(aux_I, aux_J, k, r)
            # Compute A_I to check if the candidate non basic variable produces
            # a non-singular matrix, if it does, we can replace the artificial
            # variable by the non-basic variable
            aux_A_I = _compute_A_I(A_artificial, aux_I)
            # if the A_I matrix is non-singular and the non-negativity constraints
            # are satisfied, we can replace the artificial variable by the non-basic
            if np.linalg.det(aux_A_I) != 0 :
                # compute x_I to check if the non-negativity constraints are satisfied
                x_I = _compute_X_I(aux_A_I, b)
                if np.all(x_I >= 0):
                    replacement_map[r_artificial] = k
                    break
        # Now, if some valid non-basic variable was found to replace the artificial
        # variable, we should remove it from J_valid as it can't be used to replace
        # another artificial variable
        if replacement_map[r_artificial] is not None:
            J_valid = list(set(J_valid) - set([replacement_map[r_artificial]]))

    # Now we'll replace all artificial variables that can be replaced by non-basic
    # variables
    constraints_to_drop = []
    for r_artificial in replacement_map:
        r = I_from_phase_1.index(r_artificial)
        k = replacement_map[r_artificial]
        if k:
            I_from_phase_1, J = _update_I_and_J(I_from_phase_1, J, k, r)
            # remove artificial from J so it won't come back later.
            # redundant, but it is better to be explicit than implicit
            J = list(set(J) - set([r]))
        else:
            constraints_to_drop.append(r)

    # Now we drop the constraints that contain the artificial variables that
    # could not be replaced by non-basic variables
    A_original = np.delete(A_original, constraints_to_drop, axis=0)
    b = np.delete(b, constraints_to_drop)
    # And we remove the artificial variables from the basis
    # As I_from_phase_1 is updated with original variables capable
    # of replacing the artificial variables and the artificials that 
    # could not be replaced came from redundant constraints that were
    # removed at the previous step, we can safely remove the artificial
    # variables from the basis.
    I_from_phase_1 = list(set(I_from_phase_1) - set(artificial_variables))
    I_star = I_from_phase_1
    return I_star, A_original, b

def _simplex_find_feasible_initial_basis(A: np.ndarray, b: np.ndarray, c: np.ndarray, I: list, debug = False, cycle_proof = True) -> tuple[Any, np.ndarray, np.ndarray, np.ndarray, bool, int, dict]:
    """
    Finds a feasible initial basis for the 2-phase simplex method.
    This is the first phase of the 2-phase simplex method.
    Args:
        A: the matrix of coefficients of the constraints.
        b: the vector of the right-hand side of the constraints.
        c: the vector of coefficients of the objective function.
        I: the set of indices of the basic variables.
        debug: a boolean variable to print the steps of the simplex method.
    Returns:
        I: the set of indices of the basic variables.
        A_I: the coefficients matrix of the basic variables.
        A: the coefficients matrix of the constraints after the first phase.
        b: the vector of the right-hand side of the constraints after the first phase.
        feasible: a boolean indicating if the original problem is feasible.
        iterations_count: the number of iterations needed to find a feasible basis.
        debug_info: a dictionary with debug information.
    """
    # Create copies of the input matrices so we don't modify the original ones
    A = np.copy(A)
    sanitized_A = np.copy(A)
    b = np.copy(b)
    sanitized_b = np.copy(b)
    c = np.copy(c)
    I = deepcopy(I)

    # Initialize auxiliary variables
    debug_info = {}
    m, n = A.shape
    A_I = _compute_A_I(A, I)
    x_I = _compute_X_I(A_I, b)

    # Check if the initial basis is already feasible
    if np.all(x_I >= 0):
        return I, A_I, A, b, True, 0, debug_info

    # If not, perform the first phase of the 2-phase simplex method
    """
    Perform first phase - steps:
        1. Create artificial variables
        2. Add them to the coefficients matrix A
        3. Create the artificial objective function φ of the form min 1.X
        4. Solve the auxiliary problem through the simplex method
        The original problem is feasible if φ* = 0, otherwise it is infeasible.
    """
    # 1. Create the artificial variables
    x_I_indices_lesser_than_zero = np.where(x_I < 0)[0]

    artificial_variables = np.array([
        [1 if i == j else 0 for i in range(m)] for j in x_I_indices_lesser_than_zero
    ]).T
    artificial_variables_indices = np.arange(n, n + len(x_I_indices_lesser_than_zero))
    # 2. Add the artificial variables to the coefficients matrix A
    A_artificial = np.hstack((np.copy(A), artificial_variables))
    # 3. Create the artificial objective function
    c_artificial = np.zeros(A_artificial.shape[1])
    c_artificial[n:] = 1
    # 4. Solve the auxiliary problem
    # 4.1. Replace the indices of the artificial variables in the basic variables set
    I_artificial = np.copy(I)
    I_artificial[x_I_indices_lesser_than_zero] = np.arange(n, n + len(x_I_indices_lesser_than_zero))
    # 4.2. call the simplex method
    φ_star, x_star, I_star, A_I_star, A, iterations_count, solution_type, first_phase_debug_info = _simplex_with_feasible_initial_basis(
        A_artificial, b, c_artificial, I_artificial, debug
    )
    # 4.3. Determine original problem feasibility
    feasible = φ_star == 0
    # 3. Update the debug information
    debug_info['first phase'] = {
        'first_phase_debug_info': first_phase_debug_info,
        'φ_star': φ_star,
        'x_star': x_star,
        'I_star': I_star,
        'A_I_star': A_I_star,
        'A': A,
        'A_artificial': A_artificial, 
        'b': b,
        'c_artificial': c_artificial,
        'I_artificial': I_artificial,
        'iterations_count': iterations_count,
        'solution_type': solution_type
    }

    # 4. Analyze the resulting basis
    # If the resulting basis contains some of the artificial variables and the original problem is feasible,
    # we'll try to replace the artificial basic variables by the original non-basic variables

    # 4.1 Check if the original problem is feasible
    if not feasible:
        return I, A_I, A, b, feasible, iterations_count, debug_info

    # 4.2 Check if there are artificial variables in basis
    I_restricted_to_artificial_variables_in_I = np.intersect1d(I_star,artificial_variables_indices)

    # If there aren't any artificial variables in the basis, return I_star, A_I_star, A, feasible, debug_info
    artificial_variables_in_basis = len(I_restricted_to_artificial_variables_in_I) > 0
    if not artificial_variables_in_basis:
        return I_star, A_I_star, A, b, feasible, iterations_count, debug_info

    # Else, drive the artificial variables out of the basis
    I_sanitized, sanitized_A, sanitized_b = _drive_artificial_variables_out_of_basis(
        A_artificial,
        A,
        b,
        c_artificial,
        list(I_star),
        artificial_variables_indices
    )
    A_I_sanitized = _compute_A_I(sanitized_A, I_sanitized)

    return I_sanitized, A_I_sanitized, sanitized_A, sanitized_b, feasible, iterations_count, debug_info

def _simplex_with_feasible_initial_basis(A: np.ndarray, b: np.ndarray, c: np.ndarray, I: list, debug = False, cycle_proof = True) -> tuple[float, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, int, dict]:
    """
    Solves the linear programming minimization problem where:
        A is the matrix of coefficients of the constraints,
        b is the vector of the right-hand side of the constraints,
        c is the vector of coefficients of the objective function,
        I is the set of indices of the basic variables, considering that the
        initial basis is feasible,
        debug is a boolean variable to print the steps of the simplex method.
    It returns:
        z_star: the optimal value of the objective function,
        x_star: the optimal solution,
        I_star: the set of indices of the basic variables in the optimal solution,
        A_I: the matrix of coefficients of the basic variables in the optimal solution,
        A: the matrix of coefficients of the constraints after the method,
        iterations_count: the number of iterations needed to reach the optimal solution,
        solution_type: the type of the solution
            1 - optimal finite solution found,
            2 - multiple optimal solutions found,
            3 - unbounded solution,
            -1 - infeasible solution,
        debug_info: a dictionary with debug information.
    """
    # Create copies of the input matrices so we don't modify the original ones
    A = np.copy(A)
    b = np.copy(b)
    c = np.copy(c)
    I = deepcopy(I)
    # Initialize auxiliary variables
    k = None
    r = None
    y_k = None
    old_I = None
    old_J = None
    debug_info_from_r_who_leaves = None
    solution_found = False
    debug_info = {}
    debug_info['title'] = 'Simplex method with feasible initial basis for granted'
    _, n = A.shape
    iterations_count = 0
    # Perform the simplex method
    J = _compute_J(n, I)
    while not solution_found:
        # 1. Compute A_I, A_I_inv, J, A_J, x_I, π, and z_0
        A_I, x_I, π, z_0 = _compute_A_I_x_I_π_and_z_0(A, b, c, I)
        A_I_inv = np.linalg.inv(A_I)
        A_J = _compute_A_J(A, J)
        old_I, old_J = deepcopy(I), deepcopy(J)
        # 2. Compute c_hat_J
        c_hat_J = _compute_c_hat_J(π, A, c, J)
        # 3. Find the variable to enter the basis
        k, c_hat_k_gt_0 = _find_k_who_enters(c_hat_J)
        # If c_hat_k <= 0, a solution was found
        if not c_hat_k_gt_0:
            solution_found = True
            # solution type must be 1 if all c_hat_J < 0, otherwise 2
            solution_type = 1 if np.all(c_hat_J < 0) else 2
            continue # advance to the end of the loop and exit in sequence
        # 4. Find the variable to leave the basis
        r, y_k, y_k_gt_0, debug_info_from_r_who_leaves = _find_r_who_leaves(
            I = I,
            A_I_inv = A_I_inv,
            x_I = x_I,
            A_k = A_J[:, k],
            A = A,
            k = k,
            debug = debug,
            cycle_proof = cycle_proof
        )
        # If y_k_r <= 0, the solution is unbounded
        if not y_k_gt_0:
            solution_found = True
            # our problem is unbounded, so our solution type is 3
            solution_type = 3
            continue # advance to the end of the loop and exit in sequence
        # 5. Update I and J
        I, J = _update_I_and_J(I, J, k, r)
        # 6. Append debug information for all values computed in this iteration
        h = f'debug_info_iteration_{iterations_count:02d}'
        debug_info[h] = {
            'A_I': A_I,
            'A_I_inv': A_I_inv,
            'J': J,
            'A_J': A_J,
            'x_I': x_I,
            'x': _compute_x_from_x_I(n, I, x_I),
            'π': π,
            'z_0': z_0,
            'c_hat_J': c_hat_J,
            'k': k,
            'r': r,
            'debug_info_from_r_who_leaves': debug_info_from_r_who_leaves,
            'y_k': y_k,
            'previous I': old_I,
            'previous J': old_J,
            'computed I': I,
            'computed J': J,
        }
        # 7. Increment the iterations count
        iterations_count += 1

    # 8. Append debug information for all values computed in the last iteration
    h = f'debug_info_iteration_{iterations_count:02d}'
    debug_info[h] = {
        'A_I': A_I,
        'A_I_inv': A_I_inv,
        'J': J,
        'A_J': A_J,
        'x_I': x_I,
        'x': _compute_x_from_x_I(n, I, x_I),
        'π': π,
        'z_0': z_0,
        'c_hat_J': c_hat_J,
        'k': k,
        'r': r,
        'debug_info_from_r_who_leaves': debug_info_from_r_who_leaves,
        'y_k': y_k,
        'previous I': old_I,
        'previous J': old_J,
        'computed I': I,
        'computed J': J,
    }
    # Assuming that this method takes a feasible initial I basis for granted,
    # it can only returns solution of types 1, 2, or 3. Now we should return
    # the expected values
    z_star = z_0
    x_star = x_I
    I_star = I
    A_I_star = A_I
    return z_star, x_star, I_star, A_I_star, A, iterations_count, solution_type, debug_info

def simplex(A: np.ndarray, b: np.ndarray, c: np.ndarray, I: np.ndarray, debug = False, cycle_proof = True) -> tuple[float, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, int, dict]:    
    """
    Solves the linear programming minimization problem through the 2-phases simplex where:
        A is the matrix of coefficients of the constraints,
        b is the vector of the right-hand side of the constraints,
        c is the vector of coefficients of the objective function,
        I is the set of indices of the basic variables, feasible or not,
        debug is a boolean variable to print the steps of the simplex method.
    It returns:
        z_star: the optimal value of the objective function,
        x_star: the optimal solution,
        I_star: the set of indices of the basic variables in the optimal solution,
        A_I: the matrix of coefficients of the basic variables in the optimal solution,
        A: the matrix of coefficients of the constraints after the method,
        iterations_count: the number of iterations needed to reach the optimal solution,
        solution_type: the type of the solution
            1 - optimal finite solution found,
            2 - multiple optimal solutions found,
            3 - unbounded solution,
            -1 - infeasible solution,
        debug_info: a dictionary with debug information.
    """
    # Create copies of the input matrices so we don't modify the original ones
    A = np.copy(A)
    b = np.copy(b)
    c = np.copy(c)
    I = np.copy(I)
    # Find a feasible initial basis
    I, A_I, A_artificial, b, feasible, iterations_count, debug_info = _simplex_find_feasible_initial_basis(A, b, c, I, debug, cycle_proof = True)
    # If the original problem is infeasible, return the expected values
    if not feasible:
        return 0, np.zeros(A.shape[1]), I, A_I, A, iterations_count, -1, debug_info
    # Otherwise, solve the problem with the feasible initial basis granted:
    # the second phase of the 2-phases simplex method
    z_star, x_star, I_star, A_I_star, A, iterations_count_second_phase, solution_type, debug_info_second_phase = _simplex_with_feasible_initial_basis(A, b, c, I, debug, cycle_proof = cycle_proof)
    # Append the debug information from the second phase to the debug information from the first phase
    debug_info['second phase'] = debug_info_second_phase
    return z_star, x_star, I_star, A_I_star, A, iterations_count + iterations_count_second_phase, solution_type, debug_info

def simplex2(A: np.ndarray, b: np.ndarray, c: np.ndarray, debug = False) -> tuple[float, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, int, dict]:    
    """
    Solves the linear programming minimization problem through the 2-phases simplex where:
        A is the matrix of coefficients of the constraints,
        b is the vector of the right-hand side of the constraints,
        c is the vector of coefficients of the objective function,
        debug is a boolean variable to print the steps of the simplex method.
    It returns:
        z_star: the optimal value of the objective function,
        x_star: the optimal solution,
        I_star: the set of indices of the basic variables in the optimal solution,
        A_I: the matrix of coefficients of the basic variables in the optimal solution,
        A: the matrix of coefficients of the constraints after the method,
        iterations_count: the number of iterations needed to reach the optimal solution,
        solution_type: the type of the solution
            1 - optimal finite solution found,
            2 - multiple optimal solutions found,
            3 - unbounded solution,
            -1 - infeasible solution,
        debug_info: a dictionary with debug information.
    """
    # Create copies of the input matrices so we don't modify the original ones
    m, n = A.shape
    A = np.copy(A)
    b = np.copy(b)
    c = np.copy(c)
    I = list(range(n - m, n))
    # Find a feasible initial basis
    I, A_I, A_artificial, b, feasible, iterations_count, debug_info = _simplex_find_feasible_initial_basis(A, b, c, I, debug)
    # If the original problem is infeasible, return the expected values
    if not feasible:
        return 0, np.zeros(A.shape[1]), I, A_I, A, iterations_count, -1, debug_info
    # Otherwise, solve the problem with the feasible initial basis granted:
    # the second phase of the 2-phases simplex method
    z_star, x_star, I_star, A_I_star, A, iterations_count_second_phase, solution_type, debug_info_second_phase = _simplex_with_feasible_initial_basis(A, b, c, I, debug)
    # Append the debug information from the second phase to the debug information from the first phase
    debug_info['second phase'] = debug_info_second_phase
    return z_star, x_star, I_star, A_I_star, A, iterations_count + iterations_count_second_phase, solution_type, debug_info

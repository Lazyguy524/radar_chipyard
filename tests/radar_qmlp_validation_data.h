#ifndef RADAR_QMLP_VALIDATION_DATA_H
#define RADAR_QMLP_VALIDATION_DATA_H

#include <stdint.h>

#include "../releases/input_convergence_k3_rcs21_20260406/rcs_fix_k7_rcs21_20260414/hardware_validation_20260414/large_golden/test_inputs_int8.h"
#include "../releases/input_convergence_k3_rcs21_20260406/rcs_fix_k7_rcs21_20260414/hardware_validation_20260414/large_golden/test_logits_int32.h"
#include "../releases/input_convergence_k3_rcs21_20260406/rcs_fix_k7_rcs21_20260414/hardware_validation_20260414/boundary_cases/boundary_inputs_int8.h"
#include "../releases/input_convergence_k3_rcs21_20260406/rcs_fix_k7_rcs21_20260414/hardware_validation_20260414/boundary_cases/boundary_logits_int32.h"

#define RADAR_QMLP_LARGE_GOLDEN_ROWS    ((unsigned int)radar_mlp_test_inputs_int8_rows)
#define RADAR_QMLP_BOUNDARY_ROWS        ((unsigned int)radar_mlp_boundary_inputs_int8_rows)
#define RADAR_QMLP_VALIDATION_COLS      ((unsigned int)radar_mlp_test_inputs_int8_cols)
#define RADAR_QMLP_VALIDATION_LOGIT_COLS ((unsigned int)radar_mlp_test_logits_int32_cols)
#define RADAR_QMLP_VALIDATION_BATCH_SAMPLES 8u

static inline const int8_t *radar_qmlp_large_input_row(unsigned int row)
{
  return &radar_mlp_test_inputs_int8[row * RADAR_QMLP_VALIDATION_COLS];
}

static inline const int32_t *radar_qmlp_large_logits_row(unsigned int row)
{
  return &radar_mlp_test_logits_int32[row * RADAR_QMLP_VALIDATION_LOGIT_COLS];
}

static inline const int8_t *radar_qmlp_boundary_input_row(unsigned int row)
{
  return &radar_mlp_boundary_inputs_int8[row * RADAR_QMLP_VALIDATION_COLS];
}

static inline const int32_t *radar_qmlp_boundary_logits_row(unsigned int row)
{
  return &radar_mlp_boundary_logits_int32[row * RADAR_QMLP_VALIDATION_LOGIT_COLS];
}

#endif

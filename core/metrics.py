"""Evaluation metrics and scoring functions."""

import numpy as np
from typing import Callable, Dict, List, Optional, Union
from .dtypes import Number, Array
from .exceptions import ValidationError

def _validate_inputs(y_true: np.ndarray, y_pred: np.ndarray) -> None:
    """Validate inputs to metric functions."""
    if not isinstance(y_true, np.ndarray) or not isinstance(y_pred, np.ndarray):
        raise TypeError("Inputs must be numpy arrays")
    if y_true.shape != y_pred.shape:
        raise ValueError(f"Shape mismatch: y_true {y_true.shape} != y_pred {y_pred.shape}")
    if len(y_true) == 0:
        raise ValueError("Empty arrays are not supported")

class Metric:
    """Base class for metrics."""
    
    def __init__(self, name: str):
        self.name = name
        
    def __call__(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Compute metric value."""
        _validate_inputs(y_true, y_pred)
        raise NotImplementedError

class Accuracy(Metric):
    """Classification accuracy score."""
    
    def __init__(self):
        super().__init__('accuracy')
        
    def __call__(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        _validate_inputs(y_true, y_pred)
        return np.mean(y_true == y_pred)

class MSE(Metric):
    """Mean squared error."""
    
    def __init__(self):
        super().__init__('mse')
        
    def __call__(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        _validate_inputs(y_true, y_pred)
        return np.mean((y_true - y_pred) ** 2)

class MAE(Metric):
    """Mean absolute error."""
    
    def __init__(self):
        super().__init__('mae')
        
    def __call__(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        _validate_inputs(y_true, y_pred)
        return np.mean(np.abs(y_true - y_pred))

class R2Score(Metric):
    """R² score metric."""
    
    def __init__(self):
        super().__init__('r2')
        
    def __call__(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        _validate_inputs(y_true, y_pred)
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        if ss_tot == 0:
            return 0.0
        return 1 - (ss_res / ss_tot)

class ImpurityMetric(Metric):
    """Base class for impurity metrics."""
    
    def compute_proportions(self, y: np.ndarray) -> np.ndarray:
        """Compute class proportions."""
        if len(y) == 0:
            return np.array([])
        classes, counts = np.unique(y, return_counts=True)
        return counts / len(y)

class Entropy(ImpurityMetric):
    """Entropy impurity metric."""
    
    def __init__(self):
        super().__init__('entropy')
        
    def __call__(self, y: np.ndarray, y_pred: Optional[np.ndarray] = None) -> float:
        """Compute entropy: -Σ p_i * log(p_i)."""
        proportions = self.compute_proportions(y)
        # Avoid log(0) by filtering out zero proportions
        nonzero_props = proportions[proportions > 0]
        return -np.sum(nonzero_props * np.log2(nonzero_props))

class GiniImpurity(ImpurityMetric):
    """Gini impurity metric."""
    
    def __init__(self):
        super().__init__('gini')
        
    def __call__(self, y: np.ndarray, y_pred: Optional[np.ndarray] = None) -> float:
        """Compute Gini impurity: 1 - Σ p_i^2."""
        proportions = self.compute_proportions(y)
        return 1 - np.sum(proportions ** 2)

class MisclassificationError(ImpurityMetric):
    """Misclassification error metric."""
    
    def __init__(self):
        super().__init__('misclassification')
        
    def __call__(self, y: np.ndarray, y_pred: Optional[np.ndarray] = None) -> float:
        """Compute misclassification error: 1 - max(p_i)."""
        proportions = self.compute_proportions(y)
        return 1 - np.max(proportions) if len(proportions) > 0 else 0.0

def information_gain(y_parent: np.ndarray, y_children: List[np.ndarray], 
                    impurity_metric: ImpurityMetric = Entropy()) -> float:
    """Calculate information gain for a split.
    
    Args:
        y_parent: Labels in parent node
        y_children: List of labels in child nodes
        impurity_metric: Impurity metric to use
        
    Returns:
        Information gain from the split
    """
    parent_impurity = impurity_metric(y_parent)
    
    # Weighted sum of child impurities
    n_parent = len(y_parent)
    weighted_child_impurity = sum(
        len(child) / n_parent * impurity_metric(child)
        for child in y_children
    )
    
    return parent_impurity - weighted_child_impurity

def gain_ratio(y_parent: np.ndarray, y_children: List[np.ndarray],
               impurity_metric: ImpurityMetric = Entropy()) -> float:
    """Calculate gain ratio (normalized information gain).
    
    Args:
        y_parent: Labels in parent node
        y_children: List of labels in child nodes
        impurity_metric: Impurity metric to use
        
    Returns:
        Gain ratio for the split
    """
    ig = information_gain(y_parent, y_children, impurity_metric)
    
    # Split information
    n_parent = len(y_parent)
    split_info = -sum(
        (len(child) / n_parent) * np.log2(len(child) / n_parent)
        for child in y_children
    )
    
    return ig / split_info if split_info != 0 else 0.0

def get_metric(metric: Union[str, Metric, Callable]) -> Metric:
    """Get metric instance from string, callable or Metric object."""
    if isinstance(metric, Metric):
        return metric
    elif isinstance(metric, str):
        metrics_map = {
            'accuracy': Accuracy(),
            'mse': MSE(),
            'mae': MAE(),
            'r2': R2Score()
        }
        if metric not in metrics_map:
            raise ValueError(f"Unknown metric: {metric}")
        return metrics_map[metric]
    elif callable(metric):
        return MetricWrapper(metric)
    else:
        raise ValueError("metric must be string, Metric instance or callable")

class MetricWrapper(Metric):
    """Wrapper for callable metrics."""
    
    def __init__(self, fn: Callable):
        super().__init__(fn.__name__)
        self.fn = fn
        
    def __call__(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        _validate_inputs(y_true, y_pred)
        return self.fn(y_true, y_pred)

class MetricList:
    """Container for multiple metrics."""
    
    def __init__(self, metrics: List[Union[str, Metric, Callable]]):
        self.metrics = [get_metric(m) for m in metrics]
        self.history: Dict[str, List[float]] = {m.name: [] for m in self.metrics}
        
    def __call__(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        results = {}
        for metric in self.metrics:
            try:
                score = metric(y_true, y_pred)
                self.history[metric.name].append(score)
                results[metric.name] = score
            except Exception as e:
                results[metric.name] = None
        return results

# Update __all__ list
__all__ = [
    'Metric',
    'Accuracy',
    'MSE',
    'MAE',
    'ImpurityMetric',
    'Entropy',
    'GiniImpurity',
    'MisclassificationError',
    'information_gain',
    'gain_ratio'
]
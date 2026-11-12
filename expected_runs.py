"""No bowler ID, spell performance or recent boundary outcomes in expectation model."""
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import HistGradientBoostingRegressor,HistGradientBoostingClassifier
from bopi_model import preprocess
NUM=['innings','over','wickets_in_hand','crr','rrr','first_projection_gap','batter_sr','set_batter']
CAT=['venue','hand']
def fit(train,cfg):
    er=make_pipeline(preprocess(NUM,CAT),HistGradientBoostingRegressor(loss='poisson',max_iter=cfg['max_iter'],max_leaf_nodes=cfg['expected_max_leaves'],l2_regularization=cfg['expected_l2'],random_state=cfg['seed']))
    ew=make_pipeline(preprocess(NUM,CAT),HistGradientBoostingClassifier(max_iter=cfg['max_iter'],max_leaf_nodes=cfg['expected_max_leaves'],l2_regularization=cfg['expected_l2'],random_state=cfg['seed']))
    er.fit(train,train.charged);ew.fit(train,train.wicket.gt(0).astype(int));return er,ew

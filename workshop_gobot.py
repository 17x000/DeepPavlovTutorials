# -*- coding: utf-8 -*-
"""workshop_gobot.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/github/deepmipt/dp_tutorials/blob/master/Tutorial_3_Hybrid_bot.ipynb
"""

!pip install deeppavlov

import deeppavlov

"""# Hybrid goal-oriented bot

## General architecture

<img src="https://github.com/deepmipt/dp_tutorials/blob/master/img/bot_architecture.png?raw=1" width="100%" />

Typical goal-oriented dialog system consists of three modules:

### 1. Natural Language Understanding

is responsible 
* for detecting the whole dialogue **domain**
  * _is it the restaurant reservation?_
  * _is it the weather forecasting?_,
* for detecting current user **intention**
  * _does user say hello?_
  * _is he/she asking the telephone number?_ and
* for extracting **named entities** in the last user utterane 
  * _did user specify type of food?_
  * _what date did he/she mention?_
    
Therefore, NLU may consist of three separate models: domain classifier, intent classifier and named entity recogniser (NER).
  
The NER model is also called a slot filler model. Because every output of NER can be converted to a semantic frame with slots. For example, suppose the output of the NER was the following:
  
  
      Is it windy     on weekends ?
     
      O  O  B-SUBTYPE O  B-DATE   O
    
then we can also convert it to a semantic frame:
 
     {
        "subtype": "windy",
        "date": "weekends"
      }

### 2. Dialogue Manager

is responsible
 * for deciding of the next **system action**.
   
It is often call a dialogue policy manager module. Suppose there are  four possible system actions:
  
  
    [welcome, request_place, inform_restaurant, bye]
    
Then on the current turn of the dialogue, the task of dialogue policy manager is to choose one of the four actions to do.

### 3. Natural Language Generation


is responsible for converting system action to a textual response to the user. The module can contain simple templates as well as generative models.

     welcome -> "Hello, how are you?"

## Our implementation

<img src="https://github.com/deepmipt/dp_tutorials/blob/master/img/bot_architecture2.png?raw=1" width="100%" />

The bot we'll use will consist of the following modules. 

**NLU** will contain
* a **NER model** (no domain or intent classifiers). The used NLU model is neural network based model introduced in the previous tutorial. 

The **Dialogue Manager** will consist of
* **a neural network** that takes input text representation and semantic frame and classifies over all possible system actions

The **NLG** module is
* **a template-based** module that maps actions to texts

<img src="https://github.com/deepmipt/dp_tutorials/blob/master/img/bot_architecture3.png?raw=1" width="70%" />

## Dataset

**DatasetReader** is responsible for downloading dataset
"""

from deeppavlov.dataset_readers.dstc2_reader import DSTC2DatasetReader

data = DSTC2DatasetReader().read('./dstc2')

"""DSTC2 (Dialogue State Tracking Challenge 2) data is now

* downloaded from web
* saved to ./dstc2
"""

data['train'][1]

"""**DatasetIterator** is responsible for generating batches??


"""

from overrides import overrides

from deeppavlov.core.common.registry import register
from deeppavlov.core.data.data_learning_iterator import DataLearningIterator


@register('my_dialog_iterator')
class MyDialogDatasetIterator(DataLearningIterator):

    @staticmethod
    def _dialogs(data):
        dialogs = []
        prev_resp_act = None
        for x, y in data:
            if x.get('episode_done'):
                del x['episode_done']
                prev_resp_act = None
                dialogs.append(([], []))
            x['prev_resp_act'] = prev_resp_act
            prev_resp_act = y['act']
            dialogs[-1][0].append(x)
            dialogs[-1][1].append(y)
        return dialogs

    @overrides
    def split(self, *args, **kwargs):
        self.train = self._dialogs(self.train)
        self.valid = self._dialogs(self.valid)
        self.test = self._dialogs(self.test)

iterator = MyDialogDatasetIterator(data)

x_dialog, y_dialog = iterator.train[0]
x_dialog

x_dialog[1]

y_dialog[1]

"""## Using pretrained bot from deeppavlov"""

from deeppavlov import configs, build_model


bot = build_model(configs.go_bot.gobot_dstc2, download=True)

bot(['hi, i want some food'])

bot(['I would like indian food instead'])

# reset dialogue context
bot.reset()

"""## Training bot

To train a model in the deeppavlov library, you have to create it' **config file**.

Main section of the file are:

* dataset_reader
 * configuration of dataset reader component 
* data
 * download and saving to disk
* dataset_iterator
 * configuration of dataset iterator component generator of batches
* metadata
 * extra info 
 * urls for extra data download
 * telegram configuration
*train
 * training process configuration
 * size of batches
 * number of training epochs
*chainer
 * specifies data flow
 * which components are run and in what order

**chainer** consists of separate **Components**, which are independent classes that perform independent chunks of a model pipeline.

Our Components will be:
  
* a tokenizer that splits texts to separate words (or tokens)
"""

tokenizer = {
    "class_name": "deeppavlov.models.go_bot.wrapper:DialogComponentWrapper",
    "component": { "class_name": "split_tokenizer" },
    "in": ["x"],
    "out": ["x_tokens"]
}

"""* a vocabulary of all words from the dataset (it's main goal is to convert tokens to indeces)"""

token_vocabulary = {
    "id": "token_vocab",
    "class_name": "simple_vocab",
    "fit_on": ["x_tokens"],
    "save_path": "{MODELS_PATH}/my_gobot/token.dict",
    "load_path": "{MODELS_PATH}/my_gobot/token.dict"
}

"""* a dialogue policy neural network with templates"""

network = {
    "in": ["x"],
    "in_y": ["y"],
    "out": ["y_predicted"],
    "main": True,
    "class_name": "go_bot",
    "load_path": "{MODELS_PATH}/my_gobot/model",
    "save_path": "{MODELS_PATH}/my_gobot/model",
    "debug": False,
    "word_vocab": "#token_vocab",
    "template_path": "{DOWNLOADS_PATH}/dstc2/dstc2-templates.txt",
    "template_type": "DualTemplate",
    "api_call_action": "api_call",
    "use_action_mask": False,
    "network_parameters": {
      "learning_rate": 0.005,
      "dropout_rate": 0.5,
      "l2_reg_coef": 7e-4,
      "hidden_size": 128,
      "dense_size": 160
    },
    "slot_filler": None,
    "intent_classifier": None,
    "embedder": None,
    "bow_embedder": {
      "class_name": "bow",
      "depth": "#token_vocab.__len__()",
      "with_counts": True
    },
    "slot_filler": {
      "config_path": "{DEEPPAVLOV_PATH}/configs/ner/slotfill_dstc2.json"
    }
    "tokenizer": {
      "class_name": "stream_spacy_tokenizer",
      "lowercase": False
    },
    "tracker": {
      "class_name": "featurized_tracker",
      "slot_names": ["pricerange", "this", "area", "food", "name"]
    }
}

"""As you can see important parameters of a **Component** are:

* name
 * registered name of the component
 * *it is a link to python component implementation*
* save_path
 * path to save the component
 * *sometimes is optional, for example, for tokenizers*
* load_path
 * path to load the component 
 * *sometimes is optional, for example, for tokenizers*

#### NER model

We will also use a pretrained NER model:
"""

ner_model = build_model(deeppavlov.configs.ner.slotfill_dstc2, download=True)

ner_model(['i want cheap food in chinese reastaurant in the south of town'])

# free memory
del ner_model

"""### Full pipeline config"""

basic_config = {
  "dataset_reader": {
    "class_name": "dstc2_reader",
    "data_path": "{DOWNLOADS_PATH}/dstc2"
  },
  "dataset_iterator": {
    "class_name": "my_dialog_iterator"
  },
  "chainer": {
    "in": ["x"],
    "in_y": ["y"],
    "out": ["y_predicted"],
    "pipe": [
        tokenizer,
        token_vocabulary,
        network
    ]
  },
  "train": {
    "epochs": 200,
    "batch_size": 4,

    "metrics": ["per_item_dialog_accuracy"],
    "validation_patience": 10,
    
    "val_every_n_batches": 15,
    "val_every_n_epochs": -1,

    "log_every_n_batches": 15,
    "log_every_n_epochs": -1,
    "show_examples": False,
    "validate_best": True,
    "test_best": True
  },
  "metadata": {
    "variables": {
      "ROOT_PATH": "~/.deeppavlov",
      "DOWNLOADS_PATH": "{ROOT_PATH}/downloads",
      "MODELS_PATH": "./models",
      "CONFIGS_PATH": "./configs"
    },
    "requirements": [
      "{DEEPPAVLOV_PATH}/requirements/tf.txt",
      "{DEEPPAVLOV_PATH}/requirements/fasttext.txt",
      "{DEEPPAVLOV_PATH}/requirements/spacy.txt",
      "{DEEPPAVLOV_PATH}/requirements/en_core_web_sm.txt"
    ],
    "labels": {
      "telegram_utils": "GoalOrientedBot",
      "server_utils": "GoalOrientedBot"
    },
    "download": [
      {
        "url": "http://files.deeppavlov.ai/datasets/dstc2_v2.tar.gz",
        "subdir": "{DOWNLOADS_PATH}/dstc2"
      }
    ]
  }
}

from deeppavlov import train_model, build_model

bot = train_model(basic_config, download=True)

# or load trained bot from disk
bot = build_model(basic_config)

bot(['hi, i want some cheap food'])

bot(['bye'])

# free memory
del bot


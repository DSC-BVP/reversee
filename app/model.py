import numpy as np
import pandas as pd
from PIL import Image
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
from torch.utils.data import Dataset, DataLoader
import torchvision
import torchvision.utils
import torchvision.transforms as transforms

class QueryModel():
    """
        Get top 10 similar products from the database by passing a PIL.Image
    """
    def __init__(self, model_path, dataset, *args, **kwargs):
        self.dataset = dataset
        self.model_path = model_path
        self.net = torch.load(model_path).cuda()
        self.dataloader = DataLoader(self.dataset, num_workers=0, batch_size=1, shuffle=False)
        self.data_df = pd.DataFrame(columns=['image', 'dissimilarilty'])
        self.data_list = []

    @staticmethod
    def resizeImage(image):
        return image.resize((130, 150), Image.ANTIALIAS)
    
    def ImageToTensor(self, image):
        image = self.resizeImage(image)
        transform=transforms.Compose([transforms.ToTensor()])
        return torch.reshape(transform(image), [1, 3, 150, 130])

    def getDissimilarity(self, tensor0, tensor1):
        output0, output1 = self.net(Variable(tensor0).cuda(), Variable(tensor1).cuda())
        euclidean_distance = F.pairwise_distance(output0, output1)
        return euclidean_distance.item()
    
    def _reset_state(self):
        self.dataloader = DataLoader(self.dataset, num_workers=0, batch_size=1, shuffle=False)
        self.data_list = []

    def predict(self, image):
        """ image: PIL Image """
        self._reset_state() 
        dataiter = iter(self.dataloader)
        query_image = self.ImageToTensor(image)

        self.data_list = [
            {
                'image': image_name[0],
                'dissimilarity': self.getDissimilarity(query_image, image)
            } 
            for image_name, image in dataiter
            ]

        self.data_df = pd.DataFrame(self.data_list)
        self.data_df = self.data_df.sort_values('dissimilarity').reset_index(drop=True)
        return self.data_df[:10]


class QueryDataset():
    def __init__(self, imageFolderDataset, transform=None):
        self.imageFolderDataset = imageFolderDataset
        self.transform = transform
    
    @staticmethod
    def getImage(file_name):
        return Image.open(file_name)
    
    @staticmethod
    def resizeImage(image):
        return image.resize((130, 150), Image.ANTIALIAS)

    def __getitem__(self, index):
        image_file_name = self.imageFolderDataset.imgs[index][0]
        image = self.getImage(image_file_name)
        image = self.resizeImage(image)

        if self.transform is not None:
            image = self.transform(image)

        return image_file_name, image 
    
    def __len__(self):
        return len(self.imageFolderDataset.imgs)

class SiameseNetwork(nn.Module):
    def __init__(self):
        super(SiameseNetwork, self).__init__()
        self.cnn1 = nn.Sequential(
            nn.ReflectionPad2d(1),
            nn.Conv2d(3, 4, kernel_size=3),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(4),
            
            nn.ReflectionPad2d(1),
            nn.Conv2d(4, 8, kernel_size=3),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(8),


            nn.ReflectionPad2d(1),
            nn.Conv2d(8, 8, kernel_size=3),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(8),
        )

        self.fc1 = nn.Sequential(
            nn.Linear(8*130*150, 500),
            nn.ReLU(inplace=True),

            nn.Linear(500, 500),
            nn.ReLU(inplace=True),

            nn.Linear(500, 5))

    def forward_once(self, x):
        output = self.cnn1(x)
        output = output.view(output.size()[0], -1)
        output = self.fc1(output)
        return output

    def forward(self, input1, input2):
        output1 = self.forward_once(input1)
        output2 = self.forward_once(input2)
        return output1, output2

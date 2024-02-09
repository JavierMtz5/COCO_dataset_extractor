import os
import argparse
import random
from typing import List, Any, Optional
import json
from tqdm import tqdm
import shutil


class COCOConverter:

    def __init__(self):
        
        # Read arguments
        self.parse_arguments()

        # Create output directories
        for dataset_type in ['train', 'valid', 'test']:
            os.makedirs(os.path.join(self.output_dir, dataset_type, 'images'), exist_ok=True)
            os.makedirs(os.path.join(self.output_dir, dataset_type, 'labels'), exist_ok=True)

        # Process each dataset
        self.process_dataset('train',
                             self.coco_annotation_train,
                             self.coco_image_dir_train,
                             self.single_class_name if self.create_single_class else None)
        self.process_dataset('valid', 
                             self.coco_annotation_val,
                             self.coco_image_dir_val,
                             self.single_class_name if self.create_single_class else None)
        
        self.process_dataset('test', 
                             self.coco_annotation_test,
                             self.coco_image_dir_test)
    
    def process_dataset(self, 
                        dataset_type: str, 
                        coco_annotation_file: str,
                        coco_image_dir: str, 
                        single_class_name: Optional[str] = None) -> None:
        """
        Processes the new dataset, which will be a subset of the COCO dataset with 
        only the images corresponding to the classes given by the target_classes parameter, 
        and their new labels. Note that the new labels have as many classes as the length of 
        target_classes array.
        Finally, this new dataset is converted to YOLOv8 format.
        Args:
            dataset_type (str): train/valid/test.
            coco_annotation_file (str): path to the annotations of the original COCO dataset.
            coco_image_dir (str): path to the directory which contains the images of the original COCO dataset.
            output_dir (str): directory where the new dataset will be generated.
            target_classes (List[str]): list of the classes that should be kept. All classes must exist in the 
            original COCO dataset.
        """
        print(f'\nProcessing the {dataset_type} data...')

        if dataset_type == 'test':
            # Initialize record lists
            images_record = list()

            # If only test images with target classes can be extracted
            if self.test_only_target_classes:

                if os.path.exists(coco_annotation_file):
                    with open(coco_annotation_file, 'r') as f:
                        coco_data = json.load(f)
                    test_images_to_extract = self.extract_images_filename(coco_data=coco_data,
                                                                          extract_target_images=True)
                    if self.test_num_images:
                        test_images_to_extract = random.sample(test_images_to_extract, self.test_num_images)

                else:
                    print(f'Only test images with target classes must be extracted, but the annotation file for the test set was not found in {coco_annotation_file}')

            # If all test images can be extracted
            else:
                test_images_to_extract = os.listdir(self.coco_image_dir_test) if not self.test_num_images else random.sample(os.listdir(self.coco_image_dir_test), self.test_num_images)

            for filename in tqdm(test_images_to_extract):
                original_filename = os.path.join(self.coco_image_dir_test, filename)
                new_filename = os.path.join(self.output_dir, 'test', 'images', filename)
                shutil.copy(original_filename, new_filename)
                images_record.append(new_filename)
            
            # Save YOLOv8 or COCO format lists
            with open(os.path.join(self.output_dir, f'{dataset_type}.txt'), 'w') as dataset_list:
                dataset_list.write('\n'.join(images_record))

            print(f'{dataset_type.capitalize()} images successfully stored in {os.path.join(self.output_dir, f"{dataset_type}.txt")}. Total images: {len(images_record)}')

        # Load COCO annotations if they exist
        elif os.path.exists(coco_annotation_file):
            with open(coco_annotation_file, 'r') as f:
                coco_data = json.load(f)
            print(f'Number of images present in {dataset_type} data: {len([image_info["id"] for image_info in coco_data["images"]])}')

            # Create a new category for the single class if required
            if single_class_name:
                self.create_new_class(coco_data=coco_data)

            # Get unique image IDs with/out target classes if required
            if self.target_classes:
                unique_images_with_target_classes = self.extract_images_id(coco_data=coco_data,
                                                                           extract_target_images=True)
                if self.background_percentage > 0.0:
                    unique_images_without_target_classes = self.extract_images_id(coco_data=coco_data,
                                                                                  extract_target_images=False,
                                                                                  num_img_with_target_classes=len(unique_images_with_target_classes))
                else:
                    unique_images_without_target_classes = set()

            else:
                unique_images_with_target_classes = self.extract_images_id(coco_data=coco_data,
                                                                           extract_all=True)
                unique_images_without_target_classes = set()


            # Initialize record lists
            images_record, labels_record = list(), list()
            # Iterate through unique images with target classes
            if self.target_classes: print(f'Converting annotations that contain the target classes in {dataset_type} data...')
            else: print(f'Converting annotations for all images in {dataset_type} data...')
            self.convert_annotations(unique_images=unique_images_with_target_classes,
                                     coco_data=coco_data,
                                     coco_image_dir=coco_image_dir,
                                     dataset_type=dataset_type,
                                     images_record=images_record,
                                     labels_record=labels_record,
                                     is_background=False)
            
            if unique_images_without_target_classes: 
                print(f'Converting annotations that do not have the target classes in {dataset_type} data... (Number of background images is {self.background_percentage}% of the images that contain target classes)')
                # Iterate through unique images without target classes
                self.convert_annotations(unique_images=unique_images_without_target_classes,
                                        coco_data=coco_data,
                                        coco_image_dir=coco_image_dir,
                                        dataset_type=dataset_type,
                                        images_record=images_record,
                                        labels_record=labels_record,
                                        is_background=True)
            print(f'Annotations successfully converted for {dataset_type} data')
            
            # Save YOLOv8 or COCO format lists
            with open(os.path.join(self.output_dir, f'{dataset_type}.txt'), 'w') as dataset_list:
                dataset_list.write('\n'.join(images_record))

            print(f'{dataset_type.capitalize()} images and label data successfully stored in {os.path.join(self.output_dir, f"{dataset_type}.txt")}. Total images: {len(images_record)}')
        
        else:
            print(f'Could not find a COCO-format annotation file in {coco_annotation_file}')

    def coco_to_yolo_format(self, 
                            img_info,
                            annotations, 
                            coco_data) -> str:
        label_content = ""

        # Iterate through each annotation
        for ann in annotations:
            category_id = ann['category_id']
            category_name = next((cat['name'] for cat in coco_data.get('categories', []) if cat['id'] == category_id), None)
            
            # If the category of the annotation is a target one, include the annotation in YOLOv8 format
            if category_name in self.target_classes:
                category_id = self.target_classes.index(category_name) if not self.create_single_class else 0
                # COCO format: (x, y, width, height)
                bbox = ann['bbox']
                x_center = bbox[0] + bbox[2] / 2
                y_center = bbox[1] + bbox[3] / 2
                width = bbox[2]
                height = bbox[3]

                # Normalize values to be between 0 and 1
                x_center /= img_info['width']
                y_center /= img_info['height']
                width /= img_info['width']
                height /= img_info['height']

                label_content += f"{category_id} {x_center} {y_center} {width} {height}\n"

        return label_content
    
    def extract_images_id(self, 
                          coco_data: Any,
                          extract_target_images: bool = True,
                          num_img_with_target_classes: Optional[int] = None,
                          extract_all: bool = False) -> set:
        unique_images = set()

        if extract_all:
            return set([image_info['id'] for image_info in coco_data['images']])

        # Iterate through annotations to search for target/non-target images
        for ann in coco_data.get('annotations', []):
            category_id = ann['category_id']
            category_name = next((cat['name'] for cat in coco_data.get('categories', []) if cat['id'] == category_id), None)
            
            # Check if the annotation is for any target class
            if (category_name in self.target_classes) == extract_target_images:
                image_id = ann['image_id']
                unique_images.add(image_id)
                if not extract_target_images:
                    if len(unique_images) > num_img_with_target_classes * self.background_percentage:
                        break

        return unique_images
    
    def extract_images_filename(self, 
                                coco_data: Any,
                                extract_target_images: bool = True,
                                num_img_with_target_classes: Optional[int] = None,
                                extract_all: bool = False) -> set:
        unique_images = set()

        if extract_all:
            return set([image_info['file_name'] for image_info in coco_data['images']])

        # Iterate through annotations to search for target/non-target images
        for ann in coco_data.get('annotations', []):
            category_id = ann['category_id']
            category_name = next((cat['name'] for cat in coco_data.get('categories', []) if cat['id'] == category_id), None)
            
            # Check if the annotation is for any target class
            if (category_name in self.target_classes) == extract_target_images:
                image_id = ann['image_id']
                # Find the filename of the image
                result_dict = next((img_data for img_data in coco_data['images'] if img_data['id'] == image_id), None)
                if result_dict:
                    unique_images.add(result_dict['file_name'])
                else:
                    print(f'Image information for image id {image_id} was not found in the annotations file')
                if not extract_target_images:
                    if len(unique_images) > num_img_with_target_classes * self.background_percentage:
                        break

        return unique_images
    
    def create_new_class(self, 
                         coco_data: Any) -> None:
        # Create a new category for the single class
        new_category_id = next((cat['id'] for cat in coco_data.get('categories', []) if cat['name'] == self.single_class_name), None)
        if new_category_id is None:
            new_category_id = max(cat['id'] for cat in coco_data.get('categories', [])) + 1
            new_category = {
                'id': new_category_id,
                'name': self.single_class_name,
                'supercategory': self.single_class_name,
            }
            coco_data.setdefault('categories', []).append(new_category)

    def convert_annotations(self,
                            unique_images: set,
                            coco_data: Any,
                            coco_image_dir: str,
                            dataset_type: str,
                            images_record: List[str],
                            labels_record: List[str],
                            is_background: bool) -> List[str]:
        # Iterate through unique images with target classes
        for img_id in tqdm(unique_images):
            img_info = next((img for img in coco_data.get('images', []) if img['id'] == img_id), None)
                
            if img_info:    
                # Copy image to the new directory
                img_path = os.path.join(coco_image_dir, img_info['file_name'])
                shutil.copy(img_path, os.path.join(self.output_dir, dataset_type, 'images'))
                images_record.append(os.path.join(dataset_type, 'images', img_info['file_name'])) # Record image filename

                if is_background:
                    # If it is a background image, no target class is present
                    label_content = ''

                else:
                    # Convert annotations to YOLOv8 or COCO format
                    annotations = [ann for ann in coco_data.get('annotations', []) if ann['image_id'] == img_id]
                    if self.convert_to_yolo:
                        label_content = self.coco_to_yolo_format(img_info=img_info, annotations=annotations, coco_data=coco_data)
                    else:
                        label_content = json.dumps({'annotations': annotations})

                # Save YOLOv8 or COCO format label file
                label_filename = os.path.splitext(img_info['file_name'])[0] + ('.txt' if self.convert_to_yolo else '.json')
                label_filepath = os.path.join(self.output_dir, dataset_type, 'labels' if self.convert_to_yolo else 'annotations', label_filename)
                os.makedirs(os.path.dirname(label_filepath), exist_ok=True) # Ensure the directory exists before writing the label file
                with open(label_filepath, 'w') as label_file:
                    label_file.write(label_content)
                    
                # Record label filename
                labels_record.append(label_filepath)

    def parse_arguments(self) -> argparse.Namespace:

        # Create an ArgumentParser object
        # TODO: fill text
        parser = argparse.ArgumentParser(description='Description of your script.')

        # Add arguments
        parser.add_argument('dataset_dir', type=str, help='Path to the directory where COCO dataset is located.')
        parser.add_argument('--output_dir', type=str, default='new_dataset', help='Name of the directory where the new dataset will be generated.')
        # parser.add_argument('--target_classes', type=list, help='')
        parser.add_argument('--target_classes', '--names-list', nargs='+', default=[], help='Array of strings,where each string is the name of the '
                                                                                            'class whose images that must be extracted from the original COCO dataset.')
        parser.add_argument('--background_percentage', type=float, default=0.0, help='Only applies if some classes are being extracted from COCO dataset. '
                            'The new dataset will include <background_percentage>% more images, which will not contain any of the target classes.')
        parser.add_argument('--test_num_images', type=int, help='Number of test images from the original COCO dataset to include in the new dataset.')
        parser.add_argument('--test_only_target_classes', type=bool, default=False, help='Boolean indicating whether to include only images with the target classes or any image.')
        parser.add_argument('--create_single_class', type=bool, default=False, help='Boolean indicating whether to join all the selected classes into a single class. Defaults to True.')
        parser.add_argument('--single_class_name', type=str, default='new_class', help='Only applies if create_single_class param is set to True. Name of the single class to be generated.')
        parser.add_argument('--convert_to_yolo', type=bool, default=True, help='Boolean indicating whether to convert the annotations to YOLOv8 or not.')

        # Parse the command line arguments
        args = parser.parse_args()

        print('PARAMETERS =================================================================================\n')
        print(f"Dataset Directory: {args.dataset_dir}")
        print(f"Output Directory: {args.output_dir}")
        print(f"Target Classes: {args.target_classes}")
        print(f"Background Percentage: {args.background_percentage}")
        print(f"Test Number of Images: {args.test_num_images}")
        print(f"Test Only Target Classes: {args.test_only_target_classes}")
        print(f"Create Single Class: {args.create_single_class}")
        print(f"Single Class Name: {args.single_class_name}")
        print(f"Convert to YOLO: {args.convert_to_yolo}")

        self.coco_annotation_train = os.path.join(args.dataset_dir, 'annotations', 'instances_train2017.json')
        self.coco_image_dir_train = os.path.join(args.dataset_dir, 'images', 'train2017')
        self.coco_annotation_val = os.path.join(args.dataset_dir, 'annotations', 'instances_val2017.json')
        self.coco_image_dir_val = os.path.join(args.dataset_dir, 'images', 'val2017')
        self.coco_annotation_test = os.path.join(args.dataset_dir, 'annotations', 'instances_test2017.json')
        self.coco_image_dir_test = os.path.join(args.dataset_dir, 'images', 'test2017')
        self.output_dir = args.output_dir
        self.target_classes = args.target_classes
        self.background_percentage = args.background_percentage
        self.test_num_images = args.test_num_images
        self.test_only_target_classes = args.test_only_target_classes
        self.create_single_class = args.create_single_class
        self.single_class_name = args.single_class_name
        self.convert_to_yolo = args.convert_to_yolo

    @staticmethod
    def serialize(obj):
        if isinstance(obj, (set,)):
            return list(obj)
        elif isinstance(obj, bytes):
            return obj.decode('utf-8')
        elif isinstance(obj, range):
            return list(obj)
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


if __name__ == '__main__':
    COCOConverter()

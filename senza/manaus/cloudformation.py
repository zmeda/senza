from typing import Optional, List, Dict, Iterator
from collections import OrderedDict
from datetime import datetime
from enum import Enum
import boto3

from .route53 import Route53


class ResourceType(str, Enum):
    route53_record_set = 'AWS::Route53::RecordSet'


class CloudFormationStack:

    """
    A single AWS Cloudformation Stack.

    See:
    http://boto3.readthedocs.io/en/latest/reference/services/cloudformation.html
    """

    def __init__(self,
                 stack_id: str,
                 name: str,
                 description: Optional[str],
                 parameters: Dict[str, str],
                 creation_time: datetime,
                 last_updated_time: Optional[datetime],
                 status: str,
                 stack_status_reason: Optional[str],
                 disable_rollback: bool,
                 notification_arns: List[str],
                 timeout_in_minutes: Optional[int],
                 capabilities: Optional[List[str]],
                 outputs: Optional[List[Dict]],
                 tags: Dict[str, str],
                 *,
                 region: Optional[str]):
        self.stack_id = stack_id
        self.name = name
        self.description = description
        self.parameters = parameters
        self.creation_time = creation_time
        self.last_updated_time = last_updated_time
        self.status = status
        self.stack_status_reason = stack_status_reason
        self.disable_rollback = disable_rollback
        self.notification_arns = notification_arns
        self.timeout_in_minutes = timeout_in_minutes
        self.capabilities = capabilities
        self.outputs = outputs
        self.tags = tags

        self.region = region

    def __repr__(self):
        return "<CloudFormationStack: {name}>".format_map(vars(self))

    @classmethod
    def from_boto_dict(cls,
                       stack: Dict,
                       region: Optional[str]=None) -> "CloudFormationStack":
        stack_id = stack['StackId']
        name = stack['StackName']
        description = stack.get('Description')
        parameters = OrderedDict([(p['ParameterKey'], p['ParameterValue'])
                                  for p in stack.get('Parameters', [])
                                  if not p.get('UsePreviousValue')])
        creation_time = stack['CreationTime']
        last_updated_time = stack.get('LastUpdatedTime')
        status = stack['StackStatus']
        stack_status_reason = stack.get('StackStatusReason')
        disable_rollback = stack['DisableRollback']
        notification_arns = stack['NotificationARNs']
        timeout_in_minutes = stack.get('TimeoutInMinutes')
        capabilities = stack.get('Capabilities')
        outputs = stack.get('Outputs')
        tags = OrderedDict([(t['Key'], t['Value']) for t in stack['Tags']])

        return cls(stack_id, name, description, parameters,
                   creation_time, last_updated_time, status,
                   stack_status_reason, disable_rollback, notification_arns,
                   timeout_in_minutes, capabilities, outputs, tags,
                   region=region)

    @classmethod
    def get_by_stack_name(cls,
                          name: str,
                          region: Optional[str]=None) -> "CloudFormationStack":
        """
        See:
        http://boto3.readthedocs.io/en/latest/reference/services/cloudformation.html#CloudFormation.Client.describe_stacks
        """
        client = boto3.client('cloudformation', region)

        stacks = client.describe_stacks(StackName=name)
        stack = stacks['Stacks'][0]  # type: dict

        return cls.from_boto_dict(stack, region)

    @property
    def resources(self, resource_types: Optional[List[str]] = None) -> Iterator:
        client = boto3.client('cloudformation', self.region)
        response = client.list_stack_resources(StackName=self.stack_id)
        resources = response['StackResourceSummaries']  # type: List[Dict]
        for resource in resources:
            resource_type = resource["ResourceType"]
            if resource_types is not None and resource_type not in resource_types:
                continue

            if resource_type == ResourceType.route53_record_set:
                records = Route53.get_records(name=resource['PhysicalResourceId'])
                yield next(records)
            else:
                # Ignore resources that are still not implemented in manaus
                pass


class CloudFormation:

    def __init__(self, region: Optional[str] = None):
        self.region = region

    def get_stacks(self, all: bool=False):
        client = boto3.client('cloudformation', self.region)
        if all:
            status_filter = []
        else:
            # status_filter = [st for st in cf.valid_states if st != 'DELETE_COMPLETE']
            status_filter = [
                "CREATE_IN_PROGRESS",
                "CREATE_FAILED",
                "CREATE_COMPLETE",
                "ROLLBACK_IN_PROGRESS",
                "ROLLBACK_FAILED",
                "ROLLBACK_COMPLETE",
                "DELETE_IN_PROGRESS",
                "DELETE_FAILED",
                "UPDATE_IN_PROGRESS",
                "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
                "UPDATE_COMPLETE",
                "UPDATE_ROLLBACK_IN_PROGRESS",
                "UPDATE_ROLLBACK_FAILED",
                "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS",
                "UPDATE_ROLLBACK_COMPLETE"
            ]

        kwargs = {'StackStatusFilter': status_filter}
        while 'NextToken' not in kwargs or kwargs['NextToken']:
            results = client.list_stacks(**kwargs)
            for stack in results['StackSummaries']:
                stack_id = stack['StackId']
                yield CloudFormationStack.get_by_stack_name(stack_id,
                                                            region=self.region)
            kwargs['NextToken'] = results.get('NextToken')
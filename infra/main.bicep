targetScope = 'subscription'

param location string = 'westus2'
param resourceGroupLocation string = 'eastus2'
param resourceGroupName string = 'rg-fabric-iq-poc-20260914'

@minLength(3)
@maxLength(63)
param capacityName string = 'fabiq${uniqueString(subscription().id, resourceGroupName)}'

@minLength(1)
param capacityAdmin string = 'admin@M365CPI68039016.onmicrosoft.com'

var tags = {
  workload: 'fabric-iq-poc'
  environment: 'poc'
  owner: capacityAdmin
}

resource capacityGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: resourceGroupLocation
  tags: tags
}

module capacity 'modules/capacity.bicep' = {
  name: 'fabric-iq-f2-capacity'
  scope: capacityGroup
  params: {
    location: location
    capacityName: capacityName
    capacityAdmin: capacityAdmin
    tags: tags
  }
}

output resourceGroupId string = capacityGroup.id
output capacityResourceId string = capacity.outputs.capacityResourceId
output deployedCapacityName string = capacityName